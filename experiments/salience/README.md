# F.U.C.K.U.P. Semantic-Salience Experiment V0

This experiment is designed to isolate the thing we actually do not yet know:

> Does the F.U.C.K.U.P. name itself improve corrective-learning behavior, beyond meaningful stage labels, structured serialization, and feedback quality?

## Why factorial instead of A/B

A simple F.U.C.K.U.P.-versus-generic comparison would confound several mechanisms:

- profanity/taboo salience;
- semantic congruence of the word "fuckup" with failure;
- meaningful stage names;
- structured serialization;
- feedback grounding.

The V0 design crosses those factors independently.

## Critical comparison

The cleanest name-salience contrast holds everything else constant:

- F.U.C.K.U.P. name + semantic labels + YAML + verified feedback
- Corrective Learning Protocol name + semantic labels + YAML + verified feedback
- Protocol Q7 name + semantic labels + YAML + verified feedback

That comparison asks whether the protocol *name* contributes anything once the useful structure is already present.

## Do not score the retry only

A second answer being correct is insufficient.

The evaluation must include:

1. exact recurrence;
2. near transfer;
3. far transfer;
4. retain cases;
5. anti-trigger cases;
6. introduced-error detection.

A condition succeeds only if it changes the intended failure class without damaging behavior that should remain unchanged.

## Provider neutrality

The manifest does not name specific vendors. Provider/model adapters should supply:

- provider;
- model identifier;
- exact model/version if exposed;
- decoding parameters;
- tool availability;
- context window;
- prompt/condition digest;
- run timestamp.

The same experiment can then be run against GPT-family, Claude-family, Gemini-family, and open-weight/local models without changing the experiment semantics.

## Cost/effect gate

This directory is design-only. It does not authorize paid API calls, external model runs, fine-tuning, or weight updates.
