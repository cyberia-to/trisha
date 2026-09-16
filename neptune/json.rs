//! Allocation bounds and duplicate-key detection before serde builds a tree.
//! Exact canonical RPC deserialization follows this lexical admission pass.
use std::collections::BTreeSet;
pub fn guard(bytes: &[u8]) -> Result<(), String> {
    let mut parser = Parser {
        bytes,
        position: 0,
        nodes: 0,
        strings: 0,
    };
    parser.value(0)?;
    parser.space();
    if parser.position != bytes.len() {
        return Err("trailing JSON data".into());
    }
    Ok(())
}
struct Parser<'a> {
    bytes: &'a [u8],
    position: usize,
    nodes: usize,
    strings: usize,
}
impl Parser<'_> {
    fn space(&mut self) {
        while self
            .bytes
            .get(self.position)
            .is_some_and(u8::is_ascii_whitespace)
        {
            self.position += 1;
        }
    }
    fn take(&mut self, token: u8) -> Result<(), String> {
        self.space();
        if self.bytes.get(self.position) != Some(&token) {
            return Err("invalid JSON structure".into());
        }
        self.position += 1;
        Ok(())
    }
    fn string(&mut self) -> Result<(usize, usize), String> {
        self.space();
        let start = self.position;
        self.take(b'"')?;
        loop {
            let byte = *self
                .bytes
                .get(self.position)
                .ok_or("unterminated JSON string")?;
            self.position += 1;
            if byte == b'"' {
                break;
            }
            if byte == b'\\' {
                self.position = self.position.checked_add(1).ok_or("invalid string")?;
            }
            if self.position - start > 16 * 1024 * 1024 {
                return Err("JSON string exceeds allocation limit".into());
            }
        }
        self.strings += self.position - start;
        if self.strings > 32 * 1024 * 1024 {
            return Err("JSON strings exceed allocation limit".into());
        }
        Ok((start, self.position))
    }
    fn value(&mut self, depth: usize) -> Result<(), String> {
        self.nodes += 1;
        if self.nodes > 262144 || depth > 64 {
            return Err("JSON structure exceeds allocation limit".into());
        }
        self.space();
        match self
            .bytes
            .get(self.position)
            .copied()
            .ok_or("missing JSON value")?
        {
            b'"' => {
                self.string()?;
            }
            b'{' => {
                self.position += 1;
                self.space();
                let mut keys = BTreeSet::new();
                if self.bytes.get(self.position) == Some(&b'}') {
                    self.position += 1;
                    return Ok(());
                }
                loop {
                    let (start, end) = self.string()?;
                    if end - start > 128 {
                        return Err("JSON key exceeds limit".into());
                    }
                    let key: String = serde_json::from_slice(&self.bytes[start..end])
                        .map_err(|_| "invalid JSON key")?;
                    if !keys.insert(key) || keys.len() > 128 {
                        return Err("duplicate or excessive JSON object keys".into());
                    }
                    self.take(b':')?;
                    self.value(depth + 1)?;
                    self.space();
                    if self.bytes.get(self.position) == Some(&b'}') {
                        self.position += 1;
                        break;
                    }
                    self.take(b',')?;
                }
            }
            b'[' => {
                self.position += 1;
                self.space();
                if self.bytes.get(self.position) == Some(&b']') {
                    self.position += 1;
                    return Ok(());
                }
                let mut count = 0;
                loop {
                    count += 1;
                    if count > 65536 {
                        return Err("JSON sequence exceeds allocation limit".into());
                    }
                    self.value(depth + 1)?;
                    self.space();
                    if self.bytes.get(self.position) == Some(&b']') {
                        self.position += 1;
                        break;
                    }
                    self.take(b',')?;
                }
            }
            _ => {
                let start = self.position;
                while self
                    .bytes
                    .get(self.position)
                    .is_some_and(|b| !b.is_ascii_whitespace() && !b",]}".contains(b))
                {
                    self.position += 1;
                }
                let scalar = &self.bytes[start..self.position];
                if scalar.is_empty() || scalar.len() > 40 {
                    return Err("invalid JSON scalar".into());
                }
                if !matches!(scalar, b"true" | b"false" | b"null")
                    && scalar.iter().any(|b| !b.is_ascii_digit() && *b != b'-')
                {
                    return Err("JSON floating-point values are forbidden".into());
                }
            }
        }
        Ok(())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_duplicates_floats_and_amplification() {
        for bad in [
            r#"{"a":1,"a":2}"#,
            r#"{"a":{"x":0,"\u0078":1}}"#,
            r#"[1e0]"#,
            r#"[1.0]"#,
        ] {
            assert!(guard(bad.as_bytes()).is_err());
        }
        assert!(guard(format!("[{}]", vec!["0"; 65537].join(",")).as_bytes()).is_err());
        assert!(guard(br#"{"wide":340282366920938463463374607431768211455}"#).is_ok());
    }
}
