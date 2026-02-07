import time 
from musiclang_predict import MusicLangPredictor, corpus

ml = MusicLangPredictor('musiclang/musiclang-v2')

nb_tokens_free = 1024
temperature_free = 0.9
top_p_free = 1.0
seed_free = 16

start = time.time()
score_free = ml.predict(
    None,  # Pass None for free generation, or use corpus.get_midi_path_from_corpus('bach_847') for a specific piece
    nb_tokens=nb_tokens_free,
    temperature=temperature_free,
    topp=top_p_free,
    rng_seed=seed_free
)
end = time.time()
print(f"Free music idea generated in {end - start} seconds")
score_free.to_midi('music.mid')