//! Pinned network selection and bounded template lifecycle; no network in tests.
use super::{neptune_pow_to_json, parse_digest, parse_pow_mast_paths, parse_pow_path_a};
use serde_json::Value;
use trisha_honeycrisp::{
    neptune_mine::{NeptunePow, PowMastPaths, HEIGHT},
    Digest,
};
const FIELD_P: u64 = 0xffff_ffff_0000_0001;
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rule {
    Reboot,
    Alpha,
    Tvm1,
    Beta,
    Gamma,
}
impl Rule {
    pub fn fast(self) -> bool {
        matches!(self, Self::Beta | Self::Gamma)
    }
}
pub fn rule(network: &str, height: u64) -> Result<Rule, String> {
    let boundaries = match network {
        "main" => [15000, 23401, 38000, 40300],
        "testnet-0" | "testnet" => [120, 3571, 3669, 4650],
        "regtest" | "testnet-mock" => return Ok(Rule::Gamma),
        n if n
            .strip_prefix("testnet-")
            .and_then(|s| s.parse::<u8>().ok())
            == Some(0) =>
        {
            [120, 3571, 3669, 4650]
        }
        n if n
            .strip_prefix("testnet-")
            .and_then(|s| s.parse::<u8>().ok())
            .is_some() =>
        {
            return Ok(Rule::Gamma)
        }
        _ => return Err(format!("unknown Neptune network {network}")),
    };
    Ok(if height < boundaries[0] {
        Rule::Reboot
    } else if height < boundaries[1] {
        Rule::Alpha
    } else if height < boundaries[2] {
        Rule::Tvm1
    } else if height < boundaries[3] {
        Rule::Beta
    } else {
        Rule::Gamma
    })
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backend {
    Cpu,
    Gpu,
    Combined,
}
pub fn backend(request: &str, gpu_available: bool) -> Result<Backend, String> {
    match request {
        "cpu" | "honeycrisp" => Ok(Backend::Cpu),
        "gpu" if gpu_available => Ok(Backend::Gpu),
        "gpu" => Err("requested Metal GPU is unavailable on this build/device".into()),
        "auto" if gpu_available => Ok(Backend::Combined),
        "auto" => Ok(Backend::Cpu),
        _ => Err(format!("unknown mining backend {request}")),
    }
}
pub struct Template {
    pub block: Value,
    pub parent: Digest,
    pub rule: Rule,
    pub target: Digest,
    pub mast: PowMastPaths,
    pub path: [Digest; HEIGHT],
}
fn field(v: Option<&Value>, name: &str) -> Result<u64, String> {
    v.and_then(Value::as_u64)
        .filter(|x| *x < FIELD_P)
        .ok_or_else(|| format!("missing/noncanonical {name}"))
}
impl Template {
    pub fn parse(response: Value, network: &str) -> Result<Self, String> {
        let template = response
            .get("template")
            .filter(|v| !v.is_null())
            .ok_or("node has no mining template")?;
        let block = template.get("block").ok_or("missing block")?.clone();
        let metadata = template.get("metadata").ok_or("missing metadata")?;
        let header = block.pointer("/kernel/header").ok_or("missing header")?;
        let rule = rule(network, field(header.get("height"), "height")?)?;
        let parent = parse_digest(metadata.get("prev_block"))?;
        if parent != parse_digest(header.get("prevBlockDigest"))? {
            return Err("metadata parent differs from header".into());
        }
        let mut path = parse_pow_path_a(&block)?;
        if rule.fast() {
            let version = field(metadata.get("version"), "metadata version")?;
            if version != field(header.get("version"), "header version")? {
                return Err("metadata version differs from header".into());
            }
            // Native Pow::guess writes this field; the composer may leave it zero.
            let mut words = path[26].values();
            words[4] = trisha_rs_field(version);
            path[26] = Digest::new(words);
            let l = metadata
                .get("lustration_status")
                .filter(|v| v.is_object())
                .ok_or("missing lustration status")?;
            let index = l
                .get("max_lustrating_aocl_leaf_index")
                .and_then(Value::as_u64)
                .ok_or("invalid lustration index")?;
            let amount = l
                .get("counter")
                .ok_or("missing lustration counter")?
                .to_string()
                .parse::<i128>()
                .map_err(|_| "invalid lustration counter")?;
            if amount < 0 {
                return Err("negative lustration counter".into());
            }
            let n = amount as u128;
            let expected = [
                index & 0xffff_ffff,
                index >> 32,
                n as u64 & 0xffff_ffff,
                (n >> 32) as u64 & 0xffff_ffff,
                (n >> 64) as u64 & 0xffff_ffff,
                (n >> 96) as u64,
            ];
            let actual = [
                path[27].values()[0].value(),
                path[27].values()[1].value(),
                path[27].values()[2].value(),
                path[27].values()[3].value(),
                path[27].values()[4].value(),
                path[28].values()[0].value(),
            ];
            if actual != expected {
                return Err("lustration metadata differs from authenticated header path".into());
            }
        }
        Ok(Self {
            block,
            parent,
            rule,
            target: parse_digest(metadata.get("threshold"))?,
            mast: parse_pow_mast_paths(metadata.get("pow_mast_paths"))?,
            path,
        })
    }
}
// BField type is reexported from the owner crate, independent of CLI Triton features.
fn trisha_rs_field(x: u64) -> trisha_honeycrisp::neptune_mine::Field {
    trisha_honeycrisp::neptune_mine::Field::new(x)
}

/// Reservations, including discarded stale results, consume the original cap.
/// Fetch again before submission; callbacks cannot carry a result into a newer parent.
pub fn run(
    network: &str,
    limit: u64,
    mut fetch: impl FnMut() -> Result<Value, String>,
    mut mine: impl FnMut(&Template, u64, u64) -> Result<Option<NeptunePow>, String>,
    mut submit: impl FnMut(&Value, &Value) -> Result<bool, String>,
) -> Result<NeptunePow, String> {
    let mut spent = 0;
    let mut template = Template::parse(fetch()?, network)?;
    while spent < limit {
        let count = (limit - spent).min(4096);
        let result = mine(&template, spent, count)?;
        spent += count;
        let latest = Template::parse(fetch()?, network)?;
        if let Some(pow) = result {
            if latest.parent == template.parent
                && submit(&template.block, &neptune_pow_to_json(&pow))?
            {
                return Ok(pow);
            }
        }
        template = latest;
    }
    Err(format!("mining exhausted {limit} reserved attempts"))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn response(parent: u64) -> Value {
        let d = Digest::new([trisha_rs_field(parent); 5]).to_hex();
        let zero = Digest::default().to_hex();
        serde_json::json!({"template":{"metadata":{"prev_block":d,"threshold":zero,"version":0,"lustration_status":{"counter":0,"max_lustrating_aocl_leaf_index":0},"pow_mast_paths":{"pow":vec![zero.clone();3],"header":vec![zero.clone();2],"kernel":[zero.clone()]}},"block":{"kernel":{"header":{"height":40300,"version":0,"prevBlockDigest":d,"pow":{"pathA":vec![zero;29]}}}}}})
    }
    fn pow() -> NeptunePow {
        NeptunePow {
            root: Digest::default(),
            nonce: Digest::default(),
            path_a: [Digest::default(); 29],
            path_b: [Digest::default(); 29],
        }
    }
    #[test]
    fn backend_choice_distinguishes_unavailability_from_exhaustion() {
        for available in [false, true] {
            assert_eq!(backend("cpu", available).unwrap(), Backend::Cpu);
            assert_eq!(backend("honeycrisp", available).unwrap(), Backend::Cpu);
        }
        assert_eq!(backend("auto", false).unwrap(), Backend::Cpu);
        assert_eq!(backend("auto", true).unwrap(), Backend::Combined);
        assert_eq!(backend("gpu", true).unwrap(), Backend::Gpu);
        assert!(backend("gpu", false).is_err());
        assert!(backend("unknown", true).is_err());
        // Exhaustion has no effect on backend choice: the initialized backend
        // is retained by the session, which exhausts the same global range.
    }
    #[test]
    fn pinned_fork_boundaries_and_unknown_network() {
        for (network, b) in [
            ("main", [15000, 23401, 38000, 40300]),
            ("testnet-0", [120, 3571, 3669, 4650]),
        ] {
            let rules = [
                Rule::Reboot,
                Rule::Alpha,
                Rule::Tvm1,
                Rule::Beta,
                Rule::Gamma,
            ];
            for (i, height) in b.into_iter().enumerate() {
                assert_eq!(rule(network, height - 1).unwrap(), rules[i]);
                assert_eq!(rule(network, height).unwrap(), rules[i + 1]);
            }
        }
        for n in ["regtest", "testnet-mock", "testnet-1", "testnet-255"] {
            assert_eq!(rule(n, 0).unwrap(), Rule::Gamma);
        }
        assert!(rule("testnet-256", 0).is_err());
        assert_eq!(rule("testnet-00", 0).unwrap(), Rule::Reboot);
        let mut legacy = response(1);
        legacy["template"]["block"]["kernel"]["header"]["height"] = 100.into();
        assert_eq!(Template::parse(legacy, "main").unwrap().rule, Rule::Reboot);
        // valid zero lustration does not select Beta
    }
    #[test]
    fn template_fields_are_exact_and_version_is_inserted() {
        let mut v = response(1);
        v["template"]["metadata"]["version"] = 7.into();
        v["template"]["block"]["kernel"]["header"]["version"] = 7.into();
        assert_eq!(
            Template::parse(v.clone(), "main").unwrap().path[26].values()[4].value(),
            7
        );
        v["template"]["metadata"]["lustration_status"]["counter"] =
            serde_json::from_str("12000000000000000000000000000000").unwrap();
        v["template"]["metadata"]["lustration_status"]["max_lustrating_aocl_leaf_index"] =
            1311768467463790320u64.into();
        // Independent pinned oracle codec: 3 native coins plus nontrivial u64 index.
        let words = [2596069104, 305419896, 0, 1299916539, 1981241795];
        v["template"]["block"]["kernel"]["header"]["pow"]["pathA"][27] =
            Digest::new(words.map(trisha_rs_field)).to_hex().into();
        v["template"]["block"]["kernel"]["header"]["pow"]["pathA"][28] =
            Digest::new([151, 0, 0, 0, 0].map(trisha_rs_field))
                .to_hex()
                .into();
        assert!(Template::parse(v.clone(), "main").is_ok());
        v["template"]["metadata"]["lustration_status"]["counter"] = 0.into();
        assert!(Template::parse(v, "main").is_err());
        for key in [
            "version",
            "lustration_status",
            "threshold",
            "pow_mast_paths",
        ] {
            let mut v = response(1);
            v["template"]["metadata"]
                .as_object_mut()
                .unwrap()
                .remove(key);
            assert!(Template::parse(v, "main").is_err());
        }
    }
    #[test]
    fn stale_win_is_discarded_and_rejection_retries_without_resetting_budget() {
        let parents = [1, 2, 2, 2];
        let mut fetched = 0;
        let mut ranges = Vec::new();
        let mut submitted = Vec::new();
        let result = run(
            "main",
            12288,
            || {
                let v = response(parents[fetched]);
                fetched += 1;
                Ok(v)
            },
            |t, start, count| {
                ranges.push((t.parent.values()[0].value(), start, count));
                Ok(Some(pow()))
            },
            |block, _| {
                submitted.push(
                    block
                        .pointer("/kernel/header/prevBlockDigest")
                        .unwrap()
                        .clone(),
                );
                Ok(submitted.len() == 2)
            },
        );
        assert!(result.is_ok());
        assert_eq!(ranges, [(1, 0, 4096), (2, 4096, 4096), (2, 8192, 4096)]);
        assert_eq!(submitted.len(), 2);
        assert!(submitted
            .iter()
            .all(|p| *p == response(2)["template"]["metadata"]["prev_block"]));
    }
    #[test]
    fn exhaustion_null_template_and_rpc_error_are_bounded() {
        for limit in [0, 1, 4095, 4096, 4097] {
            let mut count = 0;
            assert!(run(
                "main",
                limit,
                || Ok(response(1)),
                |_, _, n| {
                    count += n;
                    Ok(None)
                },
                |_, _| panic!("must not submit")
            )
            .is_err());
            assert_eq!(count, limit);
        }
        assert!(run(
            "main",
            1,
            || Ok(serde_json::json!({"template":null})),
            |_, _, _| panic!(),
            |_, _| panic!()
        )
        .is_err());
        assert!(run(
            "main",
            1,
            || Err("timeout".into()),
            |_, _, _| panic!(),
            |_, _| panic!()
        )
        .is_err());
    }
}
