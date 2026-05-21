// FRI fold kernel for Triton VM proving.
//
// Performs one round of split-and-fold on an XFieldElement codeword.
// Matches ProverRound::split_and_fold() in triton-vm/src/fri.rs:
//
//   scaled_offset_inv = folding_challenge * domain_point_inverses[i]
//   left  = (1 + scaled_offset_inv) * codeword[i]
//   right = (1 - scaled_offset_inv) * codeword[n/2 + i]
//   folded[i] = (left + right) * two_inverse
//
// All arithmetic in XFieldElement = GF(p^3) with irreducible x^3 - x + 1.
// Base field: Goldilocks p = 2^64 - 2^32 + 1, Montgomery representation.

// Import Goldilocks arithmetic (prepended at shader compilation):
// fn gl_add(a, b), gl_sub(a, b), gl_mul(a, b)

// ── XFieldElement arithmetic ────────────────────────────────────
//
// XFE = a·x^2 + b·x + c stored as array<vec2<u32>, 3> = [c, b, a]
// (coefficients[0] = constant, [1] = x, [2] = x^2)

// Montgomery ONE and ZERO for domain computations
const XFE_ONE_C0: vec2<u32> = vec2<u32>(0xFFFFFFFFu, 0x00000000u); // MONTY_ONE
const XFE_ONE_C1: vec2<u32> = vec2<u32>(0u, 0u);
const XFE_ONE_C2: vec2<u32> = vec2<u32>(0u, 0u);

fn xfe_add(
    a0: vec2<u32>, a1: vec2<u32>, a2: vec2<u32>,
    b0: vec2<u32>, b1: vec2<u32>, b2: vec2<u32>,
) -> array<vec2<u32>, 3> {
    return array<vec2<u32>, 3>(
        gl_add(a0, b0),
        gl_add(a1, b1),
        gl_add(a2, b2),
    );
}

fn xfe_sub(
    a0: vec2<u32>, a1: vec2<u32>, a2: vec2<u32>,
    b0: vec2<u32>, b1: vec2<u32>, b2: vec2<u32>,
) -> array<vec2<u32>, 3> {
    return array<vec2<u32>, 3>(
        gl_sub(a0, b0),
        gl_sub(a1, b1),
        gl_sub(a2, b2),
    );
}

// XFE * XFE multiplication.
// Irreducible polynomial: x^3 - x + 1
// (ax^2 + bx + c)(dx^2 + ex + f) mod (x^3 - x + 1)
//
// From twenty-first x_field_element.rs:
//   let [c, b, a] = self.coefficients;
//   let [f, e, d] = other.coefficients;
//   r0 = c*f - a*e - b*d
//   r1 = b*f + c*e - a*d + a*e + b*d
//   r2 = a*f + b*e + c*d + a*d
fn xfe_mul(
    c: vec2<u32>, b: vec2<u32>, a: vec2<u32>,
    f: vec2<u32>, e: vec2<u32>, d: vec2<u32>,
) -> array<vec2<u32>, 3> {
    let ae = gl_mul(a, e);
    let bd = gl_mul(b, d);
    let ad = gl_mul(a, d);

    let r0 = gl_sub(gl_sub(gl_mul(c, f), ae), bd);
    let r1 = gl_add(gl_add(gl_sub(gl_add(gl_mul(b, f), gl_mul(c, e)), ad), ae), bd);
    let r2 = gl_add(gl_add(gl_add(gl_mul(a, f), gl_mul(b, e)), gl_mul(c, d)), ad);

    return array<vec2<u32>, 3>(r0, r1, r2);
}

// XFE * BFE: scalar multiplication of each coefficient.
fn xfe_mul_bfe(
    c: vec2<u32>, b: vec2<u32>, a: vec2<u32>,
    s: vec2<u32>,
) -> array<vec2<u32>, 3> {
    return array<vec2<u32>, 3>(
        gl_mul(c, s),
        gl_mul(b, s),
        gl_mul(a, s),
    );
}

// ── FRI fold kernel ─────────────────────────────────────────────

struct FriParams {
    half_n: u32,      // n/2: number of output elements
    _pad0: u32,
    _pad1: u32,
    _pad2: u32,
}

// Codeword: n XFE elements, each as 3 consecutive vec2<u32>
// Layout: [xfe0_c0, xfe0_c1, xfe0_c2, xfe1_c0, xfe1_c1, xfe1_c2, ...]
@group(0) @binding(0) var<storage, read> codeword: array<vec2<u32>>;
// Domain point inverses: n/2 BFE elements (precomputed on CPU)
@group(0) @binding(1) var<storage, read> domain_inverses: array<vec2<u32>>;
// Folding challenge: 1 XFE (3 elements)
@group(0) @binding(2) var<storage, read> challenge: array<vec2<u32>, 3>;
// two_inverse: 1 XFE (3 elements) — precomputed XFE(2).inverse()
@group(0) @binding(3) var<storage, read> two_inv: array<vec2<u32>, 3>;
// Output: n/2 XFE elements
@group(0) @binding(4) var<storage, read_write> folded: array<vec2<u32>>;
@group(0) @binding(5) var<uniform> params: FriParams;

@compute @workgroup_size(64)
fn fri_fold_round(@builtin(global_invocation_id) gid: vec3<u32>) {
    let i = gid.x;
    if i >= params.half_n {
        return;
    }

    let half_n = params.half_n;

    // Load codeword[i] (first half) and codeword[n/2 + i] (second half)
    let li = i * 3u;
    let ri = (half_n + i) * 3u;
    let fw0 = codeword[li];
    let fw1 = codeword[li + 1u];
    let fw2 = codeword[li + 2u];
    let sw0 = codeword[ri];
    let sw1 = codeword[ri + 1u];
    let sw2 = codeword[ri + 2u];

    // Load folding challenge and two_inverse
    let ch0 = challenge[0];
    let ch1 = challenge[1];
    let ch2 = challenge[2];
    let ti0 = two_inv[0];
    let ti1 = two_inv[1];
    let ti2 = two_inv[2];

    // scaled_offset_inv = folding_challenge * domain_point_inverses[i]
    // This is XFE * BFE
    let dinv = domain_inverses[i];
    let soi = xfe_mul_bfe(ch0, ch1, ch2, dinv);

    // left_summand = (one + scaled_offset_inv) * codeword[i]
    let one_plus = xfe_add(XFE_ONE_C0, XFE_ONE_C1, XFE_ONE_C2, soi[0], soi[1], soi[2]);
    let left = xfe_mul(one_plus[0], one_plus[1], one_plus[2], fw0, fw1, fw2);

    // right_summand = (one - scaled_offset_inv) * codeword[n/2 + i]
    let one_minus = xfe_sub(XFE_ONE_C0, XFE_ONE_C1, XFE_ONE_C2, soi[0], soi[1], soi[2]);
    let right = xfe_mul(one_minus[0], one_minus[1], one_minus[2], sw0, sw1, sw2);

    // folded[i] = (left + right) * two_inverse
    let sum = xfe_add(left[0], left[1], left[2], right[0], right[1], right[2]);
    let result = xfe_mul(sum[0], sum[1], sum[2], ti0, ti1, ti2);

    // Write output
    let oi = i * 3u;
    folded[oi] = result[0];
    folded[oi + 1u] = result[1];
    folded[oi + 2u] = result[2];
}
