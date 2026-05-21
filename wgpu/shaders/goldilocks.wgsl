// Goldilocks field arithmetic in Montgomery representation.
//
// p = 2^64 - 2^32 + 1 = 0xFFFFFFFF00000001
//
// All field elements stored as Montgomery form: a_mont = a * 2^64 mod p.
// This matches twenty-first's BFieldElement internal representation,
// so sbox_lookup operates on correct byte patterns and MDS/round
// constants can be passed as raw_u64() without conversion.
//
// WGSL lacks native u64, so elements are vec2<u32>(lo, hi).

const GL_P_LO: u32 = 0x00000001u;
const GL_P_HI: u32 = 0xFFFFFFFFu;

// Modular addition: (a + b) mod p
// Identical in Montgomery and canonical representation.
fn gl_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
    let lo = a.x + b.x;
    let carry_lo = select(0u, 1u, lo < a.x);
    let hi = a.y + b.y + carry_lo;
    let carry_hi = select(0u, 1u, hi < a.y || (carry_lo == 1u && hi == a.y));
    var r = vec2<u32>(lo, hi);

    if carry_hi == 1u || hi > GL_P_HI || (hi == GL_P_HI && lo >= GL_P_LO) {
        let sub_lo = r.x - GL_P_LO;
        let borrow = select(0u, 1u, r.x < GL_P_LO);
        let sub_hi = r.y - GL_P_HI - borrow;
        r = vec2<u32>(sub_lo, sub_hi);
    }
    return r;
}

// Modular subtraction: (a - b) mod p
// Identical in Montgomery and canonical representation.
fn gl_sub(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
    if a.y > b.y || (a.y == b.y && a.x >= b.x) {
        let lo = a.x - b.x;
        let borrow = select(0u, 1u, a.x < b.x);
        let hi = a.y - b.y - borrow;
        return vec2<u32>(lo, hi);
    }
    // a < b: add p before subtracting
    let ap_lo = a.x + GL_P_LO;
    let carry = select(0u, 1u, ap_lo < a.x);
    let ap_hi = a.y + GL_P_HI + carry;
    let lo = ap_lo - b.x;
    let borrow = select(0u, 1u, ap_lo < b.x);
    let hi = ap_hi - b.y - borrow;
    return vec2<u32>(lo, hi);
}

// 32x32 -> 64 bit multiplication helper
fn mul32(a: u32, b: u32) -> vec2<u32> {
    let a_lo = a & 0xFFFFu;
    let a_hi = a >> 16u;
    let b_lo = b & 0xFFFFu;
    let b_hi = b >> 16u;

    let p0 = a_lo * b_lo;
    let p1 = a_lo * b_hi;
    let p2 = a_hi * b_lo;
    let p3 = a_hi * b_hi;

    let mid = p1 + (p0 >> 16u);
    let mid2 = (mid & 0xFFFFu) + p2;

    let lo = ((mid2 & 0xFFFFu) << 16u) | (p0 & 0xFFFFu);
    let hi = p3 + (mid >> 16u) + (mid2 >> 16u);
    return vec2<u32>(lo, hi);
}

// Montgomery reduction: montyred(x: u128) -> u64
//
// Reduces a 128-bit product to a 64-bit Montgomery-form result.
// Matches twenty-first's BFieldElement::montyred exactly.
//
// Algorithm (from https://eprint.iacr.org/2022/274.pdf):
//   xl = x[0..64], xh = x[64..128]
//   (a, e) = xl.overflowing_add(xl << 32)
//   b = a.wrapping_sub(a >> 32).wrapping_sub(e)
//   (r, c) = xh.overflowing_sub(b)
//   result = r.wrapping_sub(0xFFFFFFFF * c)
fn montyred(lo: vec2<u32>, hi: vec2<u32>) -> vec2<u32> {
    // xl = lo (as u64), xh = hi (as u64)
    // xl << 32 = vec2(0, lo.x)
    let shifted_lo = 0u;
    let shifted_hi = lo.x;

    // (a, e) = xl + (xl << 32)  [overflowing_add as u64]
    let a_lo = lo.x + shifted_lo;  // lo.x + 0 = lo.x
    let a_c1 = select(0u, 1u, a_lo < lo.x);  // always 0
    let a_hi = lo.y + shifted_hi + a_c1;  // lo.y + lo.x
    // overflow e: did the u64 add overflow?
    let e = select(0u, 1u, a_hi < lo.y || (a_c1 == 1u && a_hi == lo.y));

    // a >> 32 = vec2(a_hi, 0)
    let a_shr32_lo = a_hi;
    let a_shr32_hi = 0u;

    // b = a - (a >> 32) - e  [wrapping_sub]
    let b_lo = a_lo - a_shr32_lo;
    let borrow1 = select(0u, 1u, a_lo < a_shr32_lo);
    let b_hi_tmp = a_hi - a_shr32_hi - borrow1;
    let b_lo2 = b_lo - e;
    let borrow2 = select(0u, 1u, b_lo < e);
    let b_hi = b_hi_tmp - borrow2;

    // (r, c) = xh - b  [overflowing_sub as u64]
    let r_lo = hi.x - b_lo2;
    let borrow3 = select(0u, 1u, hi.x < b_lo2);
    let r_hi = hi.y - b_hi - borrow3;
    // c = did the u64 subtraction underflow?
    let c = select(0u, 1u, hi.y < b_hi + borrow3 || (borrow3 == 1u && hi.y == b_hi));

    // result = r - (0xFFFFFFFF * c)
    // 0xFFFFFFFF * c is either 0 or 0xFFFFFFFF (fits in lo word)
    let correction = 0xFFFFFFFFu * c;
    let res_lo = r_lo - correction;
    let borrow4 = select(0u, 1u, r_lo < correction);
    let res_hi = r_hi - borrow4;

    return vec2<u32>(res_lo, res_hi);
}

// Montgomery multiplication: montyred(a * b)
// For Montgomery-form inputs, this computes the Montgomery-form product.
fn gl_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
    // Full 128-bit product: a * b
    let ll = mul32(a.x, b.x);
    let lh = mul32(a.x, b.y);
    let hl = mul32(a.y, b.x);
    let hh = mul32(a.y, b.y);

    // Accumulate into 128-bit: r3:r2:r1:r0
    var r0 = ll.x;
    var r1 = ll.y;
    var r2 = hh.x;
    var r3 = hh.y;

    // Add lh << 32
    let t1 = r1 + lh.x;
    let c1 = select(0u, 1u, t1 < r1);
    r1 = t1;
    let t2 = r2 + lh.y + c1;
    let c2 = select(0u, 1u, t2 < r2 || (c1 == 1u && t2 == r2));
    r2 = t2;
    r3 = r3 + c2;

    // Add hl << 32
    let t3 = r1 + hl.x;
    let c3 = select(0u, 1u, t3 < r1);
    r1 = t3;
    let t4 = r2 + hl.y + c3;
    let c4 = select(0u, 1u, t4 < r2 || (c3 == 1u && t4 == r2));
    r2 = t4;
    r3 = r3 + c4;

    // Apply Montgomery reduction
    return montyred(vec2<u32>(r0, r1), vec2<u32>(r2, r3));
}

// Montgomery inverse via Fermat's little theorem: a^(p-2) mod p
// p-2 = 0xFFFFFFFEFFFFFFFF
fn gl_inv(a: vec2<u32>) -> vec2<u32> {
    var result = vec2<u32>(1u, 0u);
    var base = a;
    // Low 32 bits of p-2: 0xFFFFFFFF (all ones)
    for (var i = 0u; i < 32u; i = i + 1u) {
        result = gl_mul(result, base);
        base = gl_mul(base, base);
    }
    // Bit 32 of p-2 is 0 — just square
    base = gl_mul(base, base);
    // Bits 33-63 are all 1
    for (var i = 1u; i < 32u; i = i + 1u) {
        result = gl_mul(result, base);
        base = gl_mul(base, base);
    }
    return result;
}
