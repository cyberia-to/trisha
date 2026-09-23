//! Bounded versioned files for witnesses too large for command-line arguments.
use crate::error::TrishaError;
use clap::Args;
use serde::{Deserialize, Serialize};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use trident::runtime::ProgramInput;

const MAX_BYTES: u64 = 64 * 1024 * 1024;
const MODULUS: u64 = 18_446_744_069_414_584_321;

/// Parse directly into one canonical word; retain no per-element strings or
/// untagged enum buffers while decoding a potentially large witness.
pub(crate) struct Field(u64);
impl Serialize for Field {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(&self.0.to_string())
    }
}
impl<'de> Deserialize<'de> for Field {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct Word;
        impl serde::de::Visitor<'_> for Word {
            type Value = Field;
            fn expecting(&self, out: &mut std::fmt::Formatter) -> std::fmt::Result {
                out.write_str("a canonical Goldilocks integer or unsigned decimal string")
            }
            fn visit_u64<E: serde::de::Error>(self, value: u64) -> Result<Field, E> {
                if value < MODULUS {
                    Ok(Field(value))
                } else {
                    Err(E::custom("noncanonical field"))
                }
            }
            fn visit_str<E: serde::de::Error>(self, text: &str) -> Result<Field, E> {
                if text.is_empty() || text.len() > 20 || !text.bytes().all(|b| b.is_ascii_digit()) {
                    return Err(E::custom("invalid decimal field"));
                }
                self.visit_u64(text.parse().map_err(E::custom)?)
            }
        }
        deserializer.deserialize_any(Word)
    }
}
impl Field {
    pub(crate) fn value(self) -> Result<u64, TrishaError> {
        Ok(self.0)
    }
    fn from_value(value: u64) -> Self {
        Self(value)
    }
}

fn bounded_sequence<'de, D, T, const LIMIT: usize>(deserializer: D) -> Result<Vec<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    struct Sequence<T, const N: usize>(std::marker::PhantomData<T>);
    impl<'de, T: Deserialize<'de>, const N: usize> serde::de::Visitor<'de> for Sequence<T, N> {
        type Value = Vec<T>;
        fn expecting(&self, out: &mut std::fmt::Formatter) -> std::fmt::Result {
            write!(out, "a sequence of at most {N} items")
        }
        fn visit_seq<A: serde::de::SeqAccess<'de>>(
            self,
            mut access: A,
        ) -> Result<Vec<T>, A::Error> {
            use serde::de::Error;
            if access.size_hint().is_some_and(|length| length > N) {
                return Err(A::Error::custom("input sequence exceeds field limit"));
            }
            let mut items = Vec::new();
            while let Some(item) = access.next_element()? {
                if items.len() == N {
                    return Err(A::Error::custom("input sequence exceeds field limit"));
                }
                items.push(item);
            }
            Ok(items)
        }
    }
    deserializer.deserialize_seq(Sequence::<T, LIMIT>(std::marker::PhantomData))
}
const MAX_WORDS: usize = trisha_rs::convert::MAX_INPUT_WORDS;
fn fields<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Vec<Field>, D::Error> {
    bounded_sequence::<D, Field, MAX_WORDS>(d)
}
fn claim_fields<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Vec<Field>, D::Error> {
    bounded_sequence::<D, Field, { trisha_rs::recursive::MAX_CLAIM_WORDS }>(d)
}
fn hash_fields<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Vec<Field>, D::Error> {
    bounded_sequence::<D, Field, 5>(d)
}
fn digests<'de, D: serde::Deserializer<'de>>(d: D) -> Result<Vec<[Field; 5]>, D::Error> {
    bounded_sequence::<D, [Field; 5], { MAX_WORDS / 5 }>(d)
}

fn invalid() -> TrishaError {
    TrishaError::Io(
        "invalid version 1 input/claim file: require canonical fields and the documented schema"
            .into(),
    )
}
fn values(fields: Vec<Field>) -> Result<Vec<u64>, TrishaError> {
    fields.into_iter().map(Field::value).collect()
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct InputDocument {
    schema_version: u32,
    #[serde(deserialize_with = "fields")]
    public: Vec<Field>,
    #[serde(deserialize_with = "fields")]
    secret: Vec<Field>,
    #[serde(deserialize_with = "digests")]
    digests: Vec<[Field; 5]>,
}

/// Read regular files only. Metadata alone is insufficient on Unix: the path
/// may become a FIFO between inspection and open. Supported release targets use
/// nonblocking/no-follow flags, then verify the opened descriptor's identity.
pub(crate) fn read_regular_bounded(path: &Path) -> Result<Vec<u8>, String> {
    let before = std::fs::symlink_metadata(path).map_err(|_| "file cannot be inspected")?;
    if !before.is_file() {
        return Err("file must be a regular file (no symbolic links)".into());
    }
    if before.len() > MAX_BYTES {
        return Err("file exceeds 64MiB limit".into());
    }
    let mut options = std::fs::OpenOptions::new();
    options.read(true);
    // Platform ABI flags; Linux aarch64 O_NOFOLLOW differs from x86_64.
    // Values match the target libc headers; avoid adding a runtime dependency.
    #[cfg(target_os = "macos")]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(0x4 | 0x100);
    }
    #[cfg(all(target_os = "linux", target_arch = "x86_64"))]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(0x800 | 0x20000);
    }
    #[cfg(all(target_os = "linux", target_arch = "aarch64"))]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(0x800 | 0x8000);
    }
    let file = options.open(path).map_err(|_| "file cannot be opened")?;
    let after = file.metadata().map_err(|_| "file cannot be inspected")?;
    if !after.is_file() {
        return Err("file must be a regular file".into());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if before.dev() != after.dev() || before.ino() != after.ino() {
            return Err("file identity changed while opening".into());
        }
    }
    if after.len() > MAX_BYTES {
        return Err("file exceeds 64MiB limit".into());
    }
    let mut bytes = Vec::new();
    file.take(MAX_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "file cannot be read")?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err("file exceeds 64MiB limit".into());
    }
    Ok(bytes)
}

pub(crate) fn read_bounded(path: &Path) -> Result<Vec<u8>, TrishaError> {
    read_regular_bounded(path).map_err(|error| TrishaError::Io(format!("input/claim {error}")))
}

pub(crate) fn load(path: &Path) -> Result<ProgramInput, TrishaError> {
    let document: InputDocument =
        serde_json::from_slice(&read_bounded(path)?).map_err(|_| invalid())?;
    if document.schema_version != 1 {
        return Err(invalid());
    }
    if document
        .public
        .len()
        .saturating_add(document.secret.len())
        .saturating_add(document.digests.len().saturating_mul(5))
        > MAX_WORDS
    {
        return Err(TrishaError::Io("input exceeds8Mi field-word limit".into()));
    }
    let digests = document
        .digests
        .into_iter()
        .map(|digest| {
            let values = digest
                .into_iter()
                .map(Field::value)
                .collect::<Result<Vec<_>, _>>()?;
            Ok(values
                .try_into()
                .expect("serde enforces five fields per digest"))
        })
        .collect::<Result<Vec<[u64; 5]>, TrishaError>>()?;
    Ok(ProgramInput {
        public: values(document.public)?,
        secret: values(document.secret)?,
        digests,
    })
}

fn save(path: &Path, input: ProgramInput) -> Result<(), TrishaError> {
    trisha_rs::convert::validate_input(&input).map_err(TrishaError::Io)?;
    let document = InputDocument {
        schema_version: 1,
        public: input.public.into_iter().map(Field::from_value).collect(),
        secret: input.secret.into_iter().map(Field::from_value).collect(),
        digests: input
            .digests
            .into_iter()
            .map(|digest| digest.map(Field::from_value))
            .collect(),
    };
    let bytes = serde_json::to_vec(&document).map_err(|_| invalid())?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err(TrishaError::Io(
            "encoded witness exceeds 64MiB limit".into(),
        ));
    }
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    options.open(path)?.write_all(&bytes)?;
    Ok(())
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ExpectedClaim {
    schema_version: u32,
    #[serde(deserialize_with = "hash_fields")]
    program_hash: Vec<Field>,
    #[serde(deserialize_with = "claim_fields")]
    public_input: Vec<Field>,
    #[serde(deserialize_with = "claim_fields")]
    public_output: Vec<Field>,
}

#[derive(Args)]
pub struct WitnessArgs {
    /// Existing stark-triton-v7 proof file
    pub proof: PathBuf,
    /// Explicit caller-authorized full claim, in version 1 JSON format
    #[arg(long, required_unless_present = "policy", conflicts_with_all = ["policy", "commitments"])]
    pub expected_claim: Option<PathBuf>,
    /// Fixed owner policy; proof metadata cannot select the authorized program
    #[arg(
        long,
        value_enum,
        requires = "commitments",
        conflicts_with = "expected_claim"
    )]
    pub policy: Option<crate::policy_witness::Policy>,
    /// Caller-authorized kernel and, for native currency, salted UTXO digests
    #[arg(long, requires = "policy", conflicts_with = "expected_claim")]
    pub commitments: Option<PathBuf>,
    /// New private ProgramInput JSON file; existing files are not overwritten
    #[arg(long)]
    pub output: PathBuf,
}

pub fn cmd_witness(args: WitnessArgs) -> Result<(), TrishaError> {
    let (claim, policy_public) = if let Some(policy) = args.policy {
        let path = args.commitments.as_deref().ok_or_else(invalid)?;
        let (claim, public) = crate::policy_witness::expected(policy, path)?;
        (claim, Some(public))
    } else {
        let path = args.expected_claim.as_deref().ok_or_else(invalid)?;
        let expected: ExpectedClaim =
            serde_json::from_slice(&read_bounded(path)?).map_err(|_| invalid())?;
        if expected.schema_version != 1 {
            return Err(invalid());
        }
        let claim = trisha_rs::convert::to_triton_claim_native(
            &values(expected.program_hash)?,
            &values(expected.public_input)?,
            &values(expected.public_output)?,
        )
        .map_err(TrishaError::Verify)?;
        (claim, None)
    };
    // Bound transport before the legacy TOML proof-file parser allocates its fields.
    let bytes = read_bounded(&args.proof)?;
    let proof_file: crate::proof_file::ProofFile =
        toml::from_str(std::str::from_utf8(&bytes).map_err(|_| invalid())?)
            .map_err(|_| TrishaError::Verify("invalid proof file".into()))?;
    let artifact = trident::runtime::ProofData {
        claim: trident::field::proof::Claim {
            program_hash: proof_file.claim.program_hash,
            public_input: proof_file.claim.public_input,
            public_output: proof_file.claim.public_output,
        },
        proof_bytes: crate::proof_file::ProofFile::decode_proof_bytes(&proof_file.data.proof)?,
        format: proof_file.proof.format,
    };
    let mut input =
        trisha_rs::recursive::encode_proof_data(&claim, &artifact).map_err(TrishaError::Verify)?;
    if let Some(public) = policy_public {
        input.public = public;
    }
    save(&args.output, input)?;
    eprintln!(
        "Private recursive witness written to {}",
        args.output.display()
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn field_decoder_accepts_only_canonical_words_without_string_storage() {
        assert_eq!(std::mem::size_of::<Field>(), 8);
        for text in ["0", "18446744069414584320", "\"18446744069414584320\""] {
            assert!(serde_json::from_str::<Field>(text).is_ok(), "{text}");
        }
        for text in [
            "-1",
            "1.5",
            "18446744069414584321",
            "18446744073709551615",
            "\"+1\"",
            "\"-1\"",
            "\"\"",
            "\"000000000000000000001\"",
        ] {
            assert!(serde_json::from_str::<Field>(text).is_err(), "{text}");
        }
    }

    #[test]
    fn sequences_reject_before_reading_the_remaining_payload() {
        let mut reader = serde_json::Deserializer::from_str("[0,1,2,3,INVALID]");
        let error = bounded_sequence::<_, Field, 3>(&mut reader).err().unwrap();
        assert!(error
            .to_string()
            .contains("input sequence exceeds field limit"));
        let mut reader = serde_json::Deserializer::from_str("[0,1,2]");
        assert_eq!(
            bounded_sequence::<_, Field, 3>(&mut reader).unwrap().len(),
            3
        );
    }
}
