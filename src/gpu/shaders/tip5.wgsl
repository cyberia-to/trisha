// Tip5 hash function over Goldilocks field (p = 2^64 - 2^32 + 1).
//
// All field elements in Montgomery representation (matching twenty-first's
// BFieldElement internal format). Input/output via raw_u64().
//
// Sponge construction with state width 16, rate 10, capacity 6.
// 5 rounds per permutation. S-box: lookup table for elements 0..4,
// x^7 for elements 4..16. Circulant MDS matrix.

// Import goldilocks Montgomery arithmetic (prepended at shader compilation)
// fn gl_add(a, b) -> field add (same for Montgomery and canonical)
// fn gl_sub(a, b) -> field sub
// fn gl_mul(a, b) -> Montgomery multiply: montyred(a * b)

// Montgomery form of BFieldElement::ONE = 2^64 mod p = 0xFFFFFFFF
const MONTY_ONE: vec2<u32> = vec2<u32>(0xFFFFFFFFu, 0x00000000u);
// Montgomery form of BFieldElement::ZERO = 0
const MONTY_ZERO: vec2<u32> = vec2<u32>(0u, 0u);

const STATE_SIZE: u32 = 16u;
const RATE: u32 = 10u;
const DIGEST_LEN: u32 = 5u;
const NUM_ROUNDS: u32 = 5u;
const NUM_SPLIT_AND_LOOKUP: u32 = 4u;

struct Tip5Params {
    num_rows: u32,        // Number of rows to hash
    row_len: u32,         // Elements per row (in BFieldElements)
    _pad0: u32,
    _pad1: u32,
}

// 256-entry lookup table for split-and-lookup S-box
@group(0) @binding(0) var<storage, read> lookup_table: array<u32, 256>;
// MDS first column (16 values, circulant)
@group(0) @binding(1) var<storage, read> mds_column: array<vec2<u32>, 16>;
// Round constants (5 rounds * 16 = 80 values)
@group(0) @binding(2) var<storage, read> round_constants: array<vec2<u32>, 80>;
// Input rows: num_rows * row_len field elements
@group(0) @binding(3) var<storage, read> input: array<vec2<u32>>;
// Output digests: num_rows * DIGEST_LEN field elements
@group(0) @binding(4) var<storage, read_write> output: array<vec2<u32>>;
@group(0) @binding(5) var<uniform> params: Tip5Params;

// Split-and-lookup S-box: replace each byte of the field element
// using the lookup table. Operates on raw u64 representation.
fn sbox_lookup(x: vec2<u32>) -> vec2<u32> {
    // Process all 8 bytes
    let b0 = lookup_table[x.x & 0xFFu];
    let b1 = lookup_table[(x.x >> 8u) & 0xFFu];
    let b2 = lookup_table[(x.x >> 16u) & 0xFFu];
    let b3 = lookup_table[(x.x >> 24u) & 0xFFu];
    let b4 = lookup_table[x.y & 0xFFu];
    let b5 = lookup_table[(x.y >> 8u) & 0xFFu];
    let b6 = lookup_table[(x.y >> 16u) & 0xFFu];
    let b7 = lookup_table[(x.y >> 24u) & 0xFFu];
    let lo = b0 | (b1 << 8u) | (b2 << 16u) | (b3 << 24u);
    let hi = b4 | (b5 << 8u) | (b6 << 16u) | (b7 << 24u);
    return vec2<u32>(lo, hi);
}

// Power S-box: x^7 = x * x^2 * x^4
fn sbox_power(x: vec2<u32>) -> vec2<u32> {
    let x2 = gl_mul(x, x);
    let x4 = gl_mul(x2, x2);
    return gl_mul(x, gl_mul(x2, x4));
}

// Apply S-box layer: lookup for first 4, x^7 for remaining 12
fn sbox_layer(state: ptr<function, array<vec2<u32>, 16>>) {
    for (var i = 0u; i < NUM_SPLIT_AND_LOOKUP; i = i + 1u) {
        (*state)[i] = sbox_lookup((*state)[i]);
    }
    for (var i = NUM_SPLIT_AND_LOOKUP; i < STATE_SIZE; i = i + 1u) {
        (*state)[i] = sbox_power((*state)[i]);
    }
}

// Circulant MDS matrix multiplication.
// M[row][col] = mds_column[(16 + row - col) % 16]
fn mds_layer(state: ptr<function, array<vec2<u32>, 16>>) {
    var new_state: array<vec2<u32>, 16>;
    for (var row = 0u; row < STATE_SIZE; row = row + 1u) {
        var acc = vec2<u32>(0u, 0u);
        for (var col = 0u; col < STATE_SIZE; col = col + 1u) {
            let idx = (STATE_SIZE + row - col) % STATE_SIZE;
            acc = gl_add(acc, gl_mul(mds_column[idx], (*state)[col]));
        }
        new_state[row] = acc;
    }
    for (var i = 0u; i < STATE_SIZE; i = i + 1u) {
        (*state)[i] = new_state[i];
    }
}

// Add round constants for the given round
fn add_round_constants(state: ptr<function, array<vec2<u32>, 16>>, round: u32) {
    let base = round * STATE_SIZE;
    for (var i = 0u; i < STATE_SIZE; i = i + 1u) {
        (*state)[i] = gl_add((*state)[i], round_constants[base + i]);
    }
}

// Tip5 permutation: 5 rounds of (sbox, mds, add_constants)
fn tip5_permute(state: ptr<function, array<vec2<u32>, 16>>) {
    for (var round = 0u; round < NUM_ROUNDS; round = round + 1u) {
        sbox_layer(state);
        mds_layer(state);
        add_round_constants(state, round);
    }
}

// ── Merkle tree internal node hashing (fixed-length domain) ─────
//
// hash_pair(left, right) = Tip5 permutation with:
//   state[0..5]  = left digest
//   state[5..10] = right digest
//   state[10..16] = ONE (fixed-length domain separator)
//
// Used for Merkle tree construction: parent = hash_pair(left_child, right_child).
// Level-by-level dispatch: each invocation hashes one parent node.

struct MerkleParams {
    n_pairs: u32,      // Number of parent nodes to compute
    _pad0: u32,
    _pad1: u32,
    _pad2: u32,
}

// Children digests: n_pairs * 2 * DIGEST_LEN elements (left0,right0,left1,right1,...)
@group(0) @binding(6) var<storage, read> children: array<vec2<u32>>;
// Parent digests: n_pairs * DIGEST_LEN elements
@group(0) @binding(7) var<storage, read_write> parents: array<vec2<u32>>;
@group(0) @binding(8) var<uniform> merkle_params: MerkleParams;

@compute @workgroup_size(64)
fn hash_pair(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    if idx >= merkle_params.n_pairs {
        return;
    }

    // Initialize state: fixed-length domain (capacity = ONE)
    var state: array<vec2<u32>, 16>;
    let child_base = idx * 2u * DIGEST_LEN;
    // state[0..5] = left digest
    for (var i = 0u; i < DIGEST_LEN; i = i + 1u) {
        state[i] = children[child_base + i];
    }
    // state[5..10] = right digest
    for (var i = 0u; i < DIGEST_LEN; i = i + 1u) {
        state[DIGEST_LEN + i] = children[child_base + DIGEST_LEN + i];
    }
    // state[10..16] = ONE (fixed-length domain separator)
    for (var i = RATE; i < STATE_SIZE; i = i + 1u) {
        state[i] = MONTY_ONE;
    }

    tip5_permute(&state);

    // Extract digest
    let out_base = idx * DIGEST_LEN;
    for (var i = 0u; i < DIGEST_LEN; i = i + 1u) {
        parents[out_base + i] = state[i];
    }
}

// ── Variable-length row hashing (sponge) ───────────────────────

// Hash a single row using Tip5 sponge (variable-length domain).
//
// Algorithm:
// 1. Initialize state to zeros
// 2. Absorb input in chunks of RATE (10) elements:
//    - Copy chunk into state[0..10]
//    - Permute
// 3. For final partial chunk: pad with 1 then zeros, permute
// 4. Squeeze: extract state[0..5] as digest
@compute @workgroup_size(64)
fn hash_rows(@builtin(global_invocation_id) gid: vec3<u32>) {
    let row_idx = gid.x;
    if row_idx >= params.num_rows {
        return;
    }

    let row_base = row_idx * params.row_len;

    // Initialize state to zeros (variable-length domain)
    var state: array<vec2<u32>, 16>;
    for (var i = 0u; i < STATE_SIZE; i = i + 1u) {
        state[i] = vec2<u32>(0u, 0u);
    }

    // Absorb complete chunks of RATE elements
    let full_chunks = params.row_len / RATE;
    for (var chunk = 0u; chunk < full_chunks; chunk = chunk + 1u) {
        let chunk_base = row_base + chunk * RATE;
        for (var i = 0u; i < RATE; i = i + 1u) {
            state[i] = input[chunk_base + i];
        }
        tip5_permute(&state);
    }

    // Handle remainder with padding
    let remainder = params.row_len % RATE;
    let rem_base = row_base + full_chunks * RATE;

    // Copy remainder elements
    for (var i = 0u; i < remainder; i = i + 1u) {
        state[i] = input[rem_base + i];
    }
    // Padding: ONE followed by zeros (in Montgomery representation)
    state[remainder] = MONTY_ONE;
    for (var i = remainder + 1u; i < RATE; i = i + 1u) {
        state[i] = MONTY_ZERO;
    }
    tip5_permute(&state);

    // Squeeze: extract digest
    let out_base = row_idx * DIGEST_LEN;
    for (var i = 0u; i < DIGEST_LEN; i = i + 1u) {
        output[out_base + i] = state[i];
    }
}
