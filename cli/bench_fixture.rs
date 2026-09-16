use serde::Deserialize;
use std::path::PathBuf;

#[derive(Deserialize)]
#[serde(untagged)]
enum Field {
    Integer(u64),
    Decimal(String),
}

fn fields<'de, D: serde::Deserializer<'de>>(deserializer: D) -> Result<Vec<u64>, D::Error> {
    Vec::<Field>::deserialize(deserializer)?
        .into_iter()
        .map(|field| {
            let value = match field {
                Field::Integer(value) => value,
                Field::Decimal(text)
                    if !text.is_empty() && text.bytes().all(|b| b.is_ascii_digit()) =>
                {
                    text.parse().map_err(serde::de::Error::custom)?
                }
                Field::Decimal(_) => {
                    return Err(serde::de::Error::custom(
                        "expected unsigned decimal field element",
                    ));
                }
            };
            if value >= 18_446_744_069_414_584_321 {
                return Err(serde::de::Error::custom(
                    "noncanonical Goldilocks field element",
                ));
            }
            Ok(value)
        })
        .collect()
}

fn optional_fields<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<Vec<u64>>, D::Error> {
    fields(deserializer).map(Some)
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Fixture {
    pub source: PathBuf,
    pub hand: PathBuf,
    #[serde(default = "triton")]
    pub target: String,
    #[serde(deserialize_with = "fields")]
    pub input: Vec<u64>,
    /// Different program identity may change authenticated UTXO roots/witnesses.
    /// The independent reference must explain the mapping, not change semantics.
    #[serde(default, deserialize_with = "optional_fields")]
    pub hand_input: Option<Vec<u64>>,
    #[serde(default, deserialize_with = "optional_fields")]
    pub hand_secret: Option<Vec<u64>>,
    #[serde(default, deserialize_with = "optional_fields")]
    pub hand_digests: Option<Vec<u64>>,
    #[serde(default)]
    pub implementation_bound_identity: String,
    #[serde(deserialize_with = "fields")]
    pub output: Vec<u64>,
    #[serde(default, deserialize_with = "fields")]
    pub secret: Vec<u64>,
    /// Flattened digest queue, grouped into five canonical fields at load time.
    #[serde(default, deserialize_with = "fields")]
    pub digests: Vec<u64>,
    /// Append private witness streams in order; public expectations stay in this fixture.
    #[serde(default)]
    pub witness_files: Vec<PathBuf>,
    #[serde(default)]
    pub hand_prefix: String,
    #[serde(default)]
    pub hand_libraries: Vec<PathBuf>,
    #[serde(default)]
    pub expect_failure: bool,
    #[serde(default = "cycle_budget")]
    pub max_cycles: u32,
    /// Independent formula/vector origin, not a value copied from either run.
    #[serde(default)]
    pub reference: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Witness {
    #[serde(deserialize_with = "fields")]
    pub secret: Vec<u64>,
    #[serde(deserialize_with = "fields")]
    pub digests: Vec<u64>,
}

fn triton() -> String {
    "triton".into()
}

#[cfg(test)]
mod tests {
    use super::Fixture;

    fn parse(input: &str) -> Result<Fixture, toml::de::Error> {
        toml::from_str(&format!(
            "source='main.tri'\nhand='main.tasm'\ninput={input}\noutput=[]"
        ))
    }

    #[test]
    fn decimal_strings_preserve_full_canonical_field_range() {
        assert_eq!(
            parse("[\"18446744069414584320\", 0]")
                .expect("canonical elements")
                .input,
            vec![18_446_744_069_414_584_320, 0]
        );
        for invalid in [
            "[\"18446744069414584321\"]",
            "[\"18446744073709551616\"]",
            "[\"-1\"]",
            "[\" 1\"]",
            "[\"1.0\"]",
            "[-1]",
        ] {
            assert!(parse(invalid).is_err(), "accepted {invalid}");
        }
    }

    #[test]
    fn hand_streams_preserve_canonical_fields_and_optional_absence() {
        let ordinary = parse("[]").unwrap();
        assert!(ordinary.hand_input.is_none());
        let fixture: Fixture = toml::from_str("source='a'\nhand='b'\ninput=[]\noutput=[]\nhand_input=['18446744069414584320']\nhand_secret=[]\nhand_digests=[]\nimplementation_bound_identity='canonical own-program roots'").unwrap();
        assert_eq!(fixture.hand_input.unwrap(), vec![18446744069414584320]);
        assert_eq!(fixture.hand_secret, Some(vec![]));
        assert!(
            toml::from_str::<Fixture>(
                "source='a'\nhand='b'\ninput=[]\noutput=[]\nhand_input=['18446744069414584321']"
            )
            .is_err()
        );
    }

    #[test]
    fn unknown_fixture_keys_do_not_silently_skip_expectations() {
        assert!(
            toml::from_str::<Fixture>(
                "source='a'\nhand='b'\ninput=[]\noutput=[]\nexpected_failure=true"
            )
            .is_err()
        );
    }

    #[test]
    fn shared_private_witness_cannot_replace_public_expectations() {
        let parsed: super::Witness =
            toml::from_str("secret=['18446744069414584320']\ndigests=[]").unwrap();
        assert_eq!(parsed.secret, vec![18_446_744_069_414_584_320]);
        for extra in ["input=[]", "output=[]", "expect_failure=true"] {
            assert!(
                toml::from_str::<super::Witness>(&format!("secret=[]\ndigests=[]\n{extra}"))
                    .is_err()
            );
        }
        assert!(
            toml::from_str::<super::Witness>("secret=['18446744069414584321']\ndigests=[]")
                .is_err()
        );
    }
}

fn cycle_budget() -> u32 {
    1_000_000
}
