// GEMV: Matrix-vector multiply for weighted column sums.
//
// Computes result[i] = sum_j(matrix[i * ncols + j] * weights[j])
// where matrix elements are BFE and weights are XFE.
// Result is XFE per row.
//
// Each workgroup thread handles one row.

// Import Goldilocks arithmetic (included by the host at compile time)
// fn gl_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>
// fn gl_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32>

struct GemvParams {
    nrows: u32,
    ncols: u32,
    _pad0: u32,
    _pad1: u32,
}

// Matrix: nrows × ncols BFieldElements (each as vec2<u32>)
@group(0) @binding(0) var<storage, read> matrix: array<vec2<u32>>;
// Weights: ncols XFieldElements (each as 3 × vec2<u32>)
@group(0) @binding(1) var<storage, read> weights: array<vec2<u32>>;
// Output: nrows XFieldElements (each as 3 × vec2<u32>)
@group(0) @binding(2) var<storage, read_write> output: array<vec2<u32>>;
@group(0) @binding(3) var<uniform> params: GemvParams;

// BFE × XFE = XFE: scalar multiplication of extension field element by base field element.
// If bfe = a, xfe = [c0, c1, c2], then result = [a*c0, a*c1, a*c2]
fn bfe_mul_xfe(a: vec2<u32>, c0: vec2<u32>, c1: vec2<u32>, c2: vec2<u32>) -> array<vec2<u32>, 3> {
    return array<vec2<u32>, 3>(gl_mul(a, c0), gl_mul(a, c1), gl_mul(a, c2));
}

@compute @workgroup_size(64)
fn gemv_bfe(@builtin(global_invocation_id) gid: vec3<u32>) {
    let row = gid.x;
    if row >= params.nrows {
        return;
    }

    // Accumulate XFE sum for this row
    var acc0 = vec2<u32>(0u, 0u); // coefficient 0
    var acc1 = vec2<u32>(0u, 0u); // coefficient 1
    var acc2 = vec2<u32>(0u, 0u); // coefficient 2

    let row_base = row * params.ncols;

    for (var j = 0u; j < params.ncols; j = j + 1u) {
        let m = matrix[row_base + j];          // BFE
        let w_base = j * 3u;
        let w0 = weights[w_base];              // XFE coeff 0
        let w1 = weights[w_base + 1u];         // XFE coeff 1
        let w2 = weights[w_base + 2u];         // XFE coeff 2

        // BFE × XFE = [m*w0, m*w1, m*w2]
        acc0 = gl_add(acc0, gl_mul(m, w0));
        acc1 = gl_add(acc1, gl_mul(m, w1));
        acc2 = gl_add(acc2, gl_mul(m, w2));
    }

    let out_base = row * 3u;
    output[out_base] = acc0;
    output[out_base + 1u] = acc1;
    output[out_base + 2u] = acc2;
}

// XFE × XFE GEMV variant for auxiliary table.
// Matrix elements are XFE, weights are XFE, result is XFE.

// XFE multiplication: (a0 + a1*x + a2*x^2) * (b0 + b1*x + b2*x^2) mod (x^3 - x + 1)
fn xfe_mul(
    a0: vec2<u32>, a1: vec2<u32>, a2: vec2<u32>,
    b0: vec2<u32>, b1: vec2<u32>, b2: vec2<u32>,
) -> array<vec2<u32>, 3> {
    // Direct multiplication:
    //   c0 = a0*b0 + (a1*b2 + a2*b1) * (-1)   [from x^3 = x - 1, so x^3 -> -1 contribution]
    //   wait, x^3 = x - 1, so:
    //   x^3 = x - 1
    //   x^4 = x^2 - x
    //
    // Product before reduction:
    //   d0 = a0*b0
    //   d1 = a0*b1 + a1*b0
    //   d2 = a0*b2 + a1*b1 + a2*b0
    //   d3 = a1*b2 + a2*b1
    //   d4 = a2*b2
    //
    // Reduce: x^3 = x - 1, x^4 = x^2 - x
    //   c0 = d0 - d3           (d3 * x^3 -> d3*(x-1), constant part = -d3)
    //     ... wait, also d4 * x^4 -> d4*(x^2 - x), constant part = 0
    //   c0 = d0 - d3
    //   c1 = d1 + d3 - d4      (d3*x from x^3=x-1, and -d4*x from x^4=x^2-x)
    //   c2 = d2 + d4            (d4*x^2 from x^4=x^2-x)

    let d0 = gl_mul(a0, b0);
    let d1 = gl_add(gl_mul(a0, b1), gl_mul(a1, b0));
    let d2 = gl_add(gl_add(gl_mul(a0, b2), gl_mul(a1, b1)), gl_mul(a2, b0));
    let d3 = gl_add(gl_mul(a1, b2), gl_mul(a2, b1));
    let d4 = gl_mul(a2, b2);

    let c0 = gl_sub(d0, d3);
    let c1 = gl_sub(gl_add(d1, d3), d4);
    let c2 = gl_add(d2, d4);

    return array<vec2<u32>, 3>(c0, c1, c2);
}

fn xfe_add(
    a0: vec2<u32>, a1: vec2<u32>, a2: vec2<u32>,
    b0: vec2<u32>, b1: vec2<u32>, b2: vec2<u32>,
) -> array<vec2<u32>, 3> {
    return array<vec2<u32>, 3>(gl_add(a0, b0), gl_add(a1, b1), gl_add(a2, b2));
}

@compute @workgroup_size(64)
fn gemv_xfe(@builtin(global_invocation_id) gid: vec3<u32>) {
    let row = gid.x;
    if row >= params.nrows {
        return;
    }

    var acc0 = vec2<u32>(0u, 0u);
    var acc1 = vec2<u32>(0u, 0u);
    var acc2 = vec2<u32>(0u, 0u);

    let row_base = row * params.ncols * 3u; // each matrix element is 3 BFE

    for (var j = 0u; j < params.ncols; j = j + 1u) {
        // Matrix element (XFE)
        let m_base = row_base + j * 3u;
        let m0 = matrix[m_base];
        let m1 = matrix[m_base + 1u];
        let m2 = matrix[m_base + 2u];

        // Weight (XFE)
        let w_base = j * 3u;
        let w0 = weights[w_base];
        let w1 = weights[w_base + 1u];
        let w2 = weights[w_base + 2u];

        // XFE × XFE
        let prod = xfe_mul(m0, m1, m2, w0, w1, w2);

        // Accumulate
        let sum = xfe_add(acc0, acc1, acc2, prod[0], prod[1], prod[2]);
        acc0 = sum[0];
        acc1 = sum[1];
        acc2 = sum[2];
    }

    let out_base = row * 3u;
    output[out_base] = acc0;
    output[out_base + 1u] = acc1;
    output[out_base + 2u] = acc2;
}
