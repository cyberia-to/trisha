use super::*;

#[test]
fn independent_derives_emit_identical_error_layouts() {
    let inputs: Vec<DeriveInput> = vec![
        syn::parse_quote! { struct Unit; },
        syn::parse_quote! { struct Tuple<T>(T, u32); },
        syn::parse_quote! {
            struct Named { a: u32, b: Vec<u64>, #[bfield_codec(ignore)] ignored: bool }
        },
        syn::parse_quote! { enum Choice { Empty, One(u32), Pair(u32, u64) } },
    ];
    for input in inputs {
        let expected = BFieldCodecDeriveBuilder::new(input.clone()).build().to_string();
        for _ in 0..64 {
            let actual = BFieldCodecDeriveBuilder::new(input.clone()).build().to_string();
            assert_eq!(actual, expected, "derive output depends on randomized map iteration");
        }
    }
}
