# F.U.C.K.U.P. Research Map and Evidence Baseline

Date: 2026-09-23
Status: exploratory research baseline
Protocol: `F.U.C.K.U.P. = Flag → Understand → Calibrate → Know → Unlearn → Prevent`

## Objective

Determine which mechanisms could make the F.U.C.K.U.P. protocol produce real, durable corrective learning in humans and AI systems, which claims are already supported, which are only plausible, and what must be tested experimentally.

The protocol is intended to remain vendor-neutral. GPT, Claude, Gemini, open-weight language models, tool-using agents, and non-LLM systems may expose different persistence mechanisms, but the corrective-learning contract should not depend on one vendor.

## Research questions that matter

1. Does a semantically congruent and emotionally salient name improve recognition, retrieval, and correct invocation?
2. Does profanity/taboo salience add anything beyond ordinary semantic congruence and distinctiveness?
3. Do meaningful stage names and schema keys improve LLM behavior relative to opaque labels?
4. Does YAML/JSON/structured serialization improve protocol fidelity, and is any one format consistently superior?
5. When does reflection actually improve future behavior, and when does it merely produce plausible self-explanation?
6. What external verification is required before a proposed correction is allowed to become durable learning?
7. How should learning persist: context, episodic memory, retrieval, skills/instructions, adapters/fine-tuning, or weight updates?
8. How can the system avoid catastrophic forgetting, collateral regressions, and excessive "unlearning"?
9. How should the protocol handle noisy, mistaken, adversarial, or poisoned feedback?
10. How do we prove that a correction generalizes beyond the incident that caused it?
11. Should causal diagnosis seek one "root cause" or a causal/contributing-factor model?
12. What makes a prevention claim justified rather than merely aspirational?

## Evidence baseline

### 1. Salience is plausible, but direct LLM profanity evidence is missing

Human cognition research shows robust special processing for taboo/emotionally arousing words. MacKay et al. reported enhanced memory and contextual binding for taboo material, and Guillet & Arndt found that neutral peripheral information could be remembered better when encoded with arousing taboo words rather than merely negative words.

Sources:
- https://pubmed.ncbi.nlm.nih.gov/15285130/
- https://pubmed.ncbi.nlm.nih.gov/19679865/
- https://pubmed.ncbi.nlm.nih.gov/28080086/

This supports a human-side salience hypothesis. It does **not** establish that an LLM will learn F.U.C.K.U.P. better because the word is profane. That exact claim remains unverified.

### 2. Semantic labels matter to language models

Verbalizer-manipulation research shows that instruction-following models behave differently when output labels align with, are neutral to, or contradict learned semantic priors. Strong models can override some arbitrary mappings, but even large models can struggle badly with mappings that contradict prior semantics.

Source:
- https://arxiv.org/abs/2307.10558

This directly motivates comparing:
- semantically congruent F.U.C.K.U.P. labels;
- a semantically congruent but non-profane control;
- arbitrary stage labels;
- deliberately contradictory labels.

### 3. Structure matters; YAML is not magic

Prompt formatting alone can materially change model performance. Experiments comparing plain text, Markdown, JSON, and YAML found significant format sensitivity, particularly in smaller models. A published cross-model study comparing JSON, YAML, CSV, function-call forms, prefixes, and hybrid formats across ChatGPT-4o, Claude, and Gemini also found model-specific quality/efficiency trade-offs.

Sources:
- https://arxiv.org/abs/2411.10541
- https://www.elspub.com/doi/10.55092/aias20250009
- https://arxiv.org/abs/2408.11061

Therefore F.U.C.K.U.P. should define a semantic data contract independently of serialization. YAML can be the readable representation; JSON Schema or another deterministic schema can provide validation.

A 2026 preprint goes further: changing only JSON/schema key wording can alter reasoning accuracy under constrained decoding, with different model families responding differently.

Source:
- https://arxiv.org/abs/2604.14862

That is preliminary evidence, but it makes the semantic naming of fields a legitimate experimental variable.

### 4. Reflection is not equivalent to correction

Reflexion demonstrates that agents can improve by storing reflective verbal feedback in episodic memory without changing model weights. Self-Refine similarly reports gains from iterative feedback/refinement.

Sources:
- https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html
- https://arxiv.org/abs/2303.17651

However, intrinsic self-correction without external evidence can fail or degrade initially correct answers. CRITIC showed that tool-grounded critique can improve correction by interacting with external tools.

Sources:
- https://arxiv.org/abs/2310.01798
- https://arxiv.org/abs/2305.11738

Design consequence: no F.U.C.K.U.P. correction should become durable merely because the same model wrote a convincing explanation. Proposed learning needs evidence and a validation gate.

### 5. Persistent experience helps selectively, not monotonically

LifelongAgentBench finds that conventional experience replay can help, but too much or irrelevant history can degrade performance through noise and context limitations; effects differ by backbone and task.

Source:
- https://arxiv.org/abs/2505.11942

Design consequence: the repository needs retrieval, relevance, confidence, and expiry/supersession rules. "Remember every fuckup forever and inject them all" is not a learning architecture.

### 6. Unlearning is difficult and can damage neighboring capabilities

TOFU found that its tested unlearning baselines did not achieve effective unlearning in the strong sense of making a model behave as though the forget data had never been learned.

Source:
- https://arxiv.org/abs/2401.06121

Design consequence: F.U.C.K.U.P.'s **Unlearn** stage should mean "identify and retire the faulty rule/assumption at the appropriate persistence layer, while preserving valid neighboring behavior." Weight-level machine unlearning is one possible implementation, not the definition.

### 7. Feedback itself can be wrong or hostile

Recent preference-learning work shows that generalization deteriorates under noisy feedback, and separate work demonstrates feedback-poisoning attacks capable of persistently altering model behavior.

Sources:
- https://arxiv.org/abs/2510.01458
- https://arxiv.org/abs/2507.02850
- https://arxiv.org/abs/2409.00787

Design consequence: feedback is evidence to assess, not authority to obey. Durable corrections need provenance, confidence, corroboration, reversibility, and quarantine states.

### 8. Error-driven learning has strong human analogues

A meta-analysis of Error Management Training found a positive overall effect across 24 studies (N=2,183), with especially strong adaptive transfer. A meta-analysis of after-action reviews across 61 studies (915 teams, 3,499 individuals) found a substantial overall improvement and emphasized alignment plus objective performance-review evidence.

Sources:
- https://pubmed.ncbi.nlm.nih.gov/18211135/
- https://pubmed.ncbi.nlm.nih.gov/32852990/
- https://www.annualreviews.org/doi/10.1146/annurev-psych-010416-044022

This supports the protocol's core idea that mistakes can become productive learning events when followed by corrective feedback and analysis.

### 9. "One root cause" is too narrow for complex systems

Critiques of simplistic root-cause methods note that complex incidents commonly have multiple causal pathways and contributing factors. Forcing a single root cause can discard useful system information.

Source:
- https://qualitysafety.bmj.com/content/26/8/671

Design consequence: **Know** should permit causal graphs, contributing factors, competing hypotheses, and evidence for/against each hypothesis rather than requiring one metaphysical "fundamental root cause."

### 10. Prevention must be testable

CheckList showed that behavioral testing exposes failures that aggregate held-out accuracy misses; practitioners using it generated more tests and found almost three times as many bugs in one study. Contrast Sets showed that small, meaningful perturbations can reveal major generalization failures, with performance drops up to 25% on some datasets.

Sources:
- https://aclanthology.org/2020.acl-main.442/
- https://aclanthology.org/2020.findings-emnlp.117/

Design consequence: **Prevent** must emit regression tests, contrast cases, a retain set, and transfer tests. "I understand now" is not evidence of learning.

## Claims: current status

**Supported**
- Structured review/corrective feedback can improve learning.
- Language-model behavior is sensitive to semantic label alignment and prompt/schema formulation.
- Structured formats influence model behavior.
- External/tool-grounded critique can outperform unsupported introspection.
- Experience memory can improve agents, but irrelevant replay can hurt.
- Behavioral and contrast testing detect failures ordinary aggregate metrics miss.

**Plausible but unconfirmed**
- The word/acronym F.U.C.K.U.P. itself creates a useful LLM salience advantage.
- Profanity adds performance beyond semantic congruence/distinctiveness.
- The acronym's semantic alignment produces better cross-session retrieval or durable correction than a sanitized mnemonic.
- YAML is the best representation for this protocol.

**Rejected as assumptions**
- Reflection automatically means learning.
- More remembered incidents always improve an agent.
- Every correction should be persisted.
- A single "root cause" always exists.
- One successful retry proves the failure has been learned away.
- Prevention can normally guarantee recurrence is impossible in an open stochastic system.

## Candidate experiment matrix

A controlled evaluation should vary one factor at a time and then test interactions:

- **Protocol name:** F.U.C.K.U.P. vs semantically aligned non-profane control vs arbitrary acronym vs generic "Corrective Learning Protocol".
- **Stage/schema labels:** meaningful labels vs opaque labels.
- **Serialization:** prose vs Markdown vs YAML vs JSON.
- **Correction signal:** self-reflection only vs external verified feedback.
- **Persistence:** current context vs retrieval memory vs durable skill/instruction vs trainable adapter/weights.
- **Model family:** GPT, Claude, Gemini, and multiple open-weight backbones.
- **Feedback quality:** correct, noisy, ambiguous, adversarial.
- **Failure type:** factual, code, instruction-following, tool-use, planning/reasoning, retrieval.

Primary metrics should include trigger precision/recall, stage fidelity, correction rate, error-introduction rate, exact recurrence, near-transfer, far-transfer, delayed/context-reset retention, retain-set regression, resistance to bad feedback, schema validity, token/latency cost, and reversibility.

The key success criterion is not "the model generated a better second answer." It is:

> A verified correction lowers recurrence on unseen related cases while preserving valid behavior outside the corrected failure class.

## Protocol changes suggested by the evidence

Do not change the six-letter mnemonic merely to add more steps. Instead, treat validation as a mandatory gate around the six-stage loop.

Recommended semantic changes for a future protocol revision:

- **Know:** identify causal mechanism(s), contributing factors, and competing explanations; bind each to evidence and confidence.
- **Unlearn:** specify exactly what assumption, heuristic, memory, rule, adapter, or parameter-level behavior is targeted; require reversibility or rollback where possible.
- **Prevent:** install controls and tests that reduce recurrence and detect it; reserve "guarantee" for cases where a formal or deterministic constraint actually makes recurrence impossible.
- **Validation gate:** original case + contrast set + transfer set + retain/regression set must pass before a correction is marked learned.
- **Learning gate:** unverified, noisy, or adversarial feedback remains quarantined rather than directly altering durable state.

## Research frontier

The central unanswered question is now experimentally clean:

**Does the semantic coherence and taboo salience of F.U.C.K.U.P. improve corrective-learning behavior in language models beyond what can be explained by structure, meaningful labels, and ordinary mnemonic distinctiveness?**

That needs a controlled cross-model experiment. The literature supports testing it; it does not answer it for us.
