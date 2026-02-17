// Goldilocks field arithmetic: p = 2^64 - 2^32 + 1
//
// WGSL lacks native u64, so field elements are represented as
// vec2<u32> where x = lo 32 bits, y = hi 32 bits.
// When WGSL adds u64 support, swap vec2<u32> for u64 — the
// arithmetic logic stays the same.

// p = 2^64 - 2^32 + 1 = (0xFFFFFFFF, 0xFFFFFFFF) - (1, 0) + 1
//   = 0xFFFFFFFF00000001
const GL_P_LO: u32 = 0x00000001u;
const GL_P_HI: u32 = 0xFFFFFFFFu;

// Modular addition: (a + b) mod p
fn gl_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
    let lo = a.x + b.x;
    let carry_lo = select(0u, 1u, lo < a.x);
    let hi = a.y + b.y + carry_lo;
    let carry_hi = select(0u, 1u, hi < a.y || (carry_lo == 1u && hi == a.y));
    var r = vec2<u32>(lo, hi);

    // Reduce: if r >= p, subtract p
    // Since p = 0xFFFFFFFF00000001, subtracting p means:
    //   lo' = lo - 1, hi' = hi - 0xFFFFFFFF - borrow
    // But we also need to handle carry_hi (overflow past 2^64)
    if carry_hi == 1u || hi > GL_P_HI || (hi == GL_P_HI && lo >= GL_P_LO) {
        let sub_lo = r.x - GL_P_LO;
        let borrow = select(0u, 1u, r.x < GL_P_LO);
        let sub_hi = r.y - GL_P_HI - borrow;
        r = vec2<u32>(sub_lo, sub_hi);
    }
    return r;
}

// Modular subtraction: (a - b) mod p
fn gl_sub(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
    if a.y > b.y || (a.y == b.y && a.x >= b.x) {
        // a >= b, no underflow
        let lo = a.x - b.x;
        let borrow = select(0u, 1u, a.x < b.x);
        let hi = a.y - b.y - borrow;
        return vec2<u32>(lo, hi);
    }
    // a < b, add p before subtracting: (a + p - b)
    let ap_lo = a.x + GL_P_LO;
    let carry = select(0u, 1u, ap_lo < a.x);
    let ap_hi = a.y + GL_P_HI + carry;
    let lo = ap_lo - b.x;
    let borrow = select(0u, 1u, ap_lo < b.x);
    let hi = ap_hi - b.y - borrow;
    return vec2<u32>(lo, hi);
}

// 32x32 -> 64 bit multiplication helper
// Returns vec2<u32>(lo, hi)
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

// Modular multiplication: (a * b) mod p
// Uses schoolbook 64x64->128 via four 32x32->64 multiplies,
// then reduces mod p using the identity: 2^64 = 2^32 - 1 (mod p).
fn gl_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
    // a * b = (a.y * 2^32 + a.x) * (b.y * 2^32 + b.x)
    // = a.x*b.x + (a.x*b.y + a.y*b.x)*2^32 + a.y*b.y*2^64
    let ll = mul32(a.x, b.x);  // [0..63]
    let lh = mul32(a.x, b.y);  // [32..95]
    let hl = mul32(a.y, b.x);  // [32..95]
    let hh = mul32(a.y, b.y);  // [64..127]

    // Accumulate into 128-bit result: r3:r2:r1:r0 (each u32)
    var r0 = ll.x;
    var r1 = ll.y;
    var r2 = hh.x;
    var r3 = hh.y;

    // Add lh shifted left by 32 bits
    let t1 = r1 + lh.x;
    let c1 = select(0u, 1u, t1 < r1);
    r1 = t1;
    let t2 = r2 + lh.y + c1;
    let c2 = select(0u, 1u, t2 < r2 || (c1 == 1u && t2 == r2));
    r2 = t2;
    r3 = r3 + c2;

    // Add hl shifted left by 32 bits
    let t3 = r1 + hl.x;
    let c3 = select(0u, 1u, t3 < r1);
    r1 = t3;
    let t4 = r2 + hl.y + c3;
    let c4 = select(0u, 1u, t4 < r2 || (c3 == 1u && t4 == r2));
    r2 = t4;
    r3 = r3 + c4;

    // Now reduce 128-bit (r3:r2:r1:r0) mod p
    // Using: 2^64 = 2^32 - 1 (mod p)
    // hi_part = r3:r2 (bits 64-127)
    // lo_part = r1:r0 (bits 0-63)
    // result = lo_part + hi_part * (2^32 - 1) mod p
    //        = lo_part + hi_part * 2^32 - hi_part mod p
    return gl_reduce(vec2<u32>(r0, r1), vec2<u32>(r2, r3));
}

// Reduce a 128-bit value (lo64, hi64) mod p.
// Uses: 2^64 ≡ 2^32 - 1 (mod p)
fn gl_reduce(lo: vec2<u32>, hi: vec2<u32>) -> vec2<u32> {
    // hi * (2^32 - 1) = hi * 2^32 - hi
    // hi * 2^32: shift hi left by 32 bits within 128-bit space
    //   = (hi.y, hi.x, 0, 0) ... but we only need 64 bits of result
    //   Overflow past 2^64 gets reduced again.

    // Step 1: hi_shifted = hi << 32 (as 96-bit: overflow into extra word)
    let shifted_lo = vec2<u32>(0u, hi.x);
    let shifted_overflow = hi.y; // bits 96-127

    // Step 2: hi_term = shifted - hi (could underflow, handle with p)
    // hi_term = hi * 2^32 - hi = hi * (2^32 - 1)
    var term_lo = shifted_lo.x - hi.x; // 0 - hi.x
    var borrow1 = select(0u, 1u, shifted_lo.x < hi.x);
    var term_hi = shifted_lo.y - hi.y - borrow1;
    // Note: if underflow occurs, we'll handle in final reduction

    // Step 3: result = lo + hi_term
    var res_lo = lo.x + term_lo;
    var carry1 = select(0u, 1u, res_lo < lo.x);
    var res_hi = lo.y + term_hi + carry1;

    // Step 4: handle shifted_overflow (reduce recursively)
    // overflow * 2^64 ≡ overflow * (2^32 - 1) mod p
    if shifted_overflow > 0u {
        let ov_lo = 0u - shifted_overflow; // -overflow mod 2^32
        let ov_borrow = select(0u, 1u, shifted_overflow > 0u);
        let ov_hi = shifted_overflow - ov_borrow; // overflow * 2^32 contribution

        let t_lo = res_lo + ov_lo;
        let c = select(0u, 1u, t_lo < res_lo);
        res_lo = t_lo;
        res_hi = res_hi + ov_hi + c;
    }

    var r = vec2<u32>(res_lo, res_hi);

    // Final reduction: subtract p while r >= p
    loop {
        if r.y > GL_P_HI || (r.y == GL_P_HI && r.x >= GL_P_LO) {
            let sub_lo = r.x - GL_P_LO;
            let b = select(0u, 1u, r.x < GL_P_LO);
            let sub_hi = r.y - GL_P_HI - b;
            r = vec2<u32>(sub_lo, sub_hi);
        } else {
            break;
        }
    }
    return r;
}

// Modular inverse via Fermat's little theorem: a^(p-2) mod p
// p-2 = 0xFFFFFFFEFFFFFFFF
fn gl_inv(a: vec2<u32>) -> vec2<u32> {
    // Square-and-multiply for a^(p-2)
    var result = vec2<u32>(1u, 0u); // 1
    var base = a;
    // p-2 in binary: 63 one-bits, then 0, then 32 one-bits
    // Low 32 bits: 0xFFFFFFFF (all ones)
    // High 32 bits: 0xFFFFFFFE (all ones except bit 0)

    // Process low 32 bits (all 1s)
    for (var i = 0u; i < 32u; i = i + 1u) {
        result = gl_mul(result, base);
        base = gl_mul(base, base);
    }
    // Process high 32 bits: 0xFFFFFFFE = 1111...1110
    // Bit 32 (LSB of high word) is 0 — just square
    base = gl_mul(base, base);
    // Bits 33-63 are all 1
    for (var i = 1u; i < 32u; i = i + 1u) {
        result = gl_mul(result, base);
        base = gl_mul(base, base);
    }
    return result;
}
