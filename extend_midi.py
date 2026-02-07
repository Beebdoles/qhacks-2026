import time
from musiclang_predict import MusicLangPredictor
from musiclang import Score

ml = MusicLangPredictor('musiclang/musiclang-v2')

input_midi = 'twinkle_midi.mid'
output_midi = 'twinkle_extended.mid'

# Approximate tokens for 10 seconds of music (roughly 50-100 tokens per second depending on complexity)
nb_tokens = 340
temperature = 0.9
top_p = 1.0
seed = 42

print(f"Loading {input_midi} and generating continuation...")
start = time.time()

# Load the original score
original_score = Score.from_midi(input_midi)

# Generate continuation based on the original
generated_score = ml.predict(
    input_midi,
    nb_tokens=nb_tokens,
    temperature=temperature,
    topp=top_p,
    rng_seed=seed
)

# Concatenate original + generated continuation
combined_score = original_score + generated_score

end = time.time()
print(f"Extended music generated in {end - start:.2f} seconds")

combined_score.to_midi(output_midi)
print(f"Saved extended MIDI to {output_midi}")
