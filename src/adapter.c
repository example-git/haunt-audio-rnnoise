// SPDX-License-Identifier: BSD-3-Clause
#include <math.h>
#include <string.h>
#include "rnnoise.h"

static DenoiseState *state;
static float input[480], output[480], scaled[480], filtered[480];
// RNNoise's analysis overlap plus one lookahead frame delays output by 20 ms.
// Align dry audio before blending; mixing current input would cause combing.
static float dry[2][480];
static unsigned cursor;
static float probability;

int audio_init(void) {
    if (state) rnnoise_destroy(state);
    state = rnnoise_create(NULL);
    memset(dry, 0, sizeof(dry));
    memset(input, 0, sizeof(input));
    memset(output, 0, sizeof(output));
    cursor = 0;
    probability = 0;
    return state != NULL && rnnoise_get_frame_size() == 480;
}
float *audio_input(void) { return input; }
float *audio_output(void) { return output; }
float audio_probability(void) { return probability; }
void audio_reset(void) { audio_init(); }
int audio_process(float strength) {
    if (!state || !isfinite(strength)) return -1;
    strength = fminf(1.f, fmaxf(0.f, strength));
    for (int i = 0; i < 480; ++i) {
        if (!isfinite(input[i])) return -1;
        scaled[i] = fminf(1.f, fmaxf(-1.f, input[i])) * 32768.f;
    }
    probability = rnnoise_process_frame(state, filtered, scaled);
    for (int i = 0; i < 480; ++i) {
        float sample = strength * (filtered[i] / 32768.f) + (1.f - strength) * dry[cursor][i];
        if (!isfinite(sample)) return -1;
        output[i] = fminf(1.f, fmaxf(-1.f, sample));
        dry[cursor][i] = input[i];
    }
    cursor = (cursor + 1) % 2;
    return 0;
}
