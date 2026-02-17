// GPU nonce mining kernel for Tip5.
//
// Each thread hashes (base_message ++ nonce) via Tip5 sponge and checks
// if digest[0] < difficulty_target. First thread to find a solution writes
// the winning nonce via atomic compare-exchange.
//
// Nonce per thread = nonce_offset_mont + mont(thread_id), where
// nonce_offset_mont is uploaded in Montgomery form by the CPU.
// mont(thread_id) = montyred(thread_id * R^2) via gl_mul.
//
// Goldilocks: R = 2^64 mod p = 2^32 - 1, R^2 mod p = 0xFFFFFFFE00000001.

struct MineParams {
    msg_len: u32,           // Base message length (field elements)
    nonce_offset_lo: u32,   // Montgomery form of nonce_offset (low)
    nonce_offset_hi: u32,   // Montgomery form of nonce_offset (high)
    target_lo: u32,         // Difficulty target, canonical (low)
}

struct MineTarget {
    target_hi: u32,         // Difficulty target, canonical (high)
    _pad0: u32,
    _pad1: u32,
    _pad2: u32,
}

@group(0) @binding(0) var<storage, read> base_message: array<vec2<u32>>;
@group(0) @binding(1) var<storage, read> mine_lookup: array<u32, 256>;
@group(0) @binding(2) var<storage, read> mine_mds: array<vec2<u32>, 16>;
@group(0) @binding(3) var<storage, read> mine_rc: array<vec2<u32>, 80>;
@group(0) @binding(4) var<uniform> mine_params: MineParams;
@group(0) @binding(5) var<uniform> mine_target: MineTarget;
// result[0] = found flag, [1..2] = nonce lo/hi, [3..12] = digest (5 × vec2)
@group(0) @binding(6) var<storage, read_write> result: array<atomic<u32>>;

const M_STATE: u32 = 16u;
const M_RATE: u32 = 10u;
const M_DIGEST: u32 = 5u;
const M_ROUNDS: u32 = 5u;
const M_LOOKUP_N: u32 = 4u;
const M_ONE: vec2<u32> = vec2<u32>(0xFFFFFFFFu, 0x00000000u);
const M_ZERO: vec2<u32> = vec2<u32>(0u, 0u);
const R_SQUARED: vec2<u32> = vec2<u32>(0x00000001u, 0xFFFFFFFEu);

fn m_sbox_lookup(x: vec2<u32>) -> vec2<u32> {
    let b0 = mine_lookup[x.x & 0xFFu];
    let b1 = mine_lookup[(x.x >> 8u) & 0xFFu];
    let b2 = mine_lookup[(x.x >> 16u) & 0xFFu];
    let b3 = mine_lookup[(x.x >> 24u) & 0xFFu];
    let b4 = mine_lookup[x.y & 0xFFu];
    let b5 = mine_lookup[(x.y >> 8u) & 0xFFu];
    let b6 = mine_lookup[(x.y >> 16u) & 0xFFu];
    let b7 = mine_lookup[(x.y >> 24u) & 0xFFu];
    return vec2<u32>(
        b0 | (b1 << 8u) | (b2 << 16u) | (b3 << 24u),
        b4 | (b5 << 8u) | (b6 << 16u) | (b7 << 24u),
    );
}

fn m_sbox_power(x: vec2<u32>) -> vec2<u32> {
    let x2 = gl_mul(x, x);
    let x4 = gl_mul(x2, x2);
    return gl_mul(x, gl_mul(x2, x4));
}

fn m_sbox(state: ptr<function, array<vec2<u32>, 16>>) {
    for (var i = 0u; i < M_LOOKUP_N; i++) { (*state)[i] = m_sbox_lookup((*state)[i]); }
    for (var i = M_LOOKUP_N; i < M_STATE; i++) { (*state)[i] = m_sbox_power((*state)[i]); }
}

fn m_mds(state: ptr<function, array<vec2<u32>, 16>>) {
    var ns: array<vec2<u32>, 16>;
    for (var r = 0u; r < M_STATE; r++) {
        var a = vec2<u32>(0u, 0u);
        for (var c = 0u; c < M_STATE; c++) {
            a = gl_add(a, gl_mul(mine_mds[(M_STATE + r - c) % M_STATE], (*state)[c]));
        }
        ns[r] = a;
    }
    for (var i = 0u; i < M_STATE; i++) { (*state)[i] = ns[i]; }
}

fn m_permute(state: ptr<function, array<vec2<u32>, 16>>) {
    for (var round = 0u; round < M_ROUNDS; round++) {
        m_sbox(state);
        m_mds(state);
        let base = round * M_STATE;
        for (var i = 0u; i < M_STATE; i++) {
            (*state)[i] = gl_add((*state)[i], mine_rc[base + i]);
        }
    }
}

// Convert Montgomery form to canonical: montyred(mont * 1) = mont * R^{-1} = canonical
fn to_canonical(mont: vec2<u32>) -> vec2<u32> {
    return gl_mul(mont, vec2<u32>(1u, 0u));
}

@compute @workgroup_size(256)
fn mine(@builtin(global_invocation_id) gid: vec3<u32>) {
    if atomicLoad(&result[0]) != 0u { return; }

    // Compute this thread's nonce in Montgomery form
    let thread_mont = gl_mul(vec2<u32>(gid.x, 0u), R_SQUARED);
    let nonce_mont = gl_add(vec2<u32>(mine_params.nonce_offset_lo, mine_params.nonce_offset_hi), thread_mont);

    // Tip5 sponge: hash(base_message ++ nonce)
    var state: array<vec2<u32>, 16>;
    for (var i = 0u; i < M_STATE; i++) { state[i] = M_ZERO; }

    let total_len = mine_params.msg_len + 1u;

    // Absorb complete chunks
    var pos = 0u;
    loop {
        if pos + M_RATE > total_len { break; }
        for (var i = 0u; i < M_RATE; i++) {
            let idx = pos + i;
            if idx < mine_params.msg_len {
                state[i] = base_message[idx];
            } else {
                state[i] = nonce_mont;
            }
        }
        m_permute(&state);
        pos += M_RATE;
    }

    // Final partial chunk with padding
    let rem = total_len - pos;
    for (var i = 0u; i < M_RATE; i++) {
        let idx = pos + i;
        if idx < mine_params.msg_len {
            state[i] = base_message[idx];
        } else if idx == mine_params.msg_len {
            state[i] = nonce_mont;
        } else if i == rem {
            state[i] = M_ONE;
        } else {
            state[i] = M_ZERO;
        }
    }
    m_permute(&state);

    // Difficulty check: canonical(digest[0]) < target
    let d0 = to_canonical(state[0]);
    var hit = false;
    if d0.y < mine_target.target_hi {
        hit = true;
    } else if d0.y == mine_target.target_hi && d0.x < mine_params.target_lo {
        hit = true;
    }

    if hit {
        let prev = atomicCompareExchangeWeak(&result[0], 0u, 1u);
        if prev.exchanged {
            atomicStore(&result[1], nonce_mont.x);
            atomicStore(&result[2], nonce_mont.y);
            for (var i = 0u; i < M_DIGEST; i++) {
                atomicStore(&result[3u + i * 2u], state[i].x);
                atomicStore(&result[3u + i * 2u + 1u], state[i].y);
            }
        }
    }
}
