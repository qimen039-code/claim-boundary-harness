# Behavior correction source map

Access date: 2026-07-16

This file records external mechanism provenance. These sources are
`source_prior` or `inspiration`; they do not validate the local CBH
implementation. Local behavior claims still require code, contract, and test
evidence.

| CBH mechanism | Source | Intake class | Absorbed element | Explicit boundary |
| --- | --- | --- | --- | --- |
| Action-level correction before execution | Alshiekh et al., [Safe Reinforcement Learning via Shielding](https://ojs.aaai.org/index.php/AAAI/article/view/11797), AAAI 2018 | inspiration | A separate reactive layer observes a proposed action and intervenes only when the action violates a specified property. This supports profile-scoped current-candidate rewrite, validation, or review instead of globally changing the model or banning every similar token. | CBH profiles are hand-authored mechanical matchers, not synthesized temporal-logic shields. No convergence or formal safety guarantee transfers. |
| Scoped review and safe fallback | NASA NTRS, [A Formal Verification Framework for Runtime Assurance](https://ntrs.nasa.gov/citations/20240006522), 2024 | source_prior | Runtime Assurance separates an untrusted/high-performance controller from a trusted monitor that can take control when a safety property is threatened. This supports a narrow current-event correction and read-only diagnosis when a declared profile matches. | CBH has no verified continuous dynamics, certified backup controller, or host-wide control guarantee. The bundled callback passes direct regression tests; host lifecycle registration remains adopter- and version-specific. Other surfaces remain model-owned direct calls. |
| Small trusted core and explicit boundaries | Saltzer and Schroeder, [The Protection of Information in Computer Systems](https://doi.org/10.1109/PROC.1975.9939), 1975 | source_prior | Least privilege and economy of mechanism support keeping profile matching small, source-bound, and separate from unrelated authorization or memory state. | CBH does not claim complete mediation or an authorization layer. Risk classification and execution authority remain separate from profile matching. |
| PowerShell syntax verifier | Microsoft, [Parser.ParseInput](https://learn.microsoft.com/en-us/dotnet/api/system.management.automation.language.parser.parseinput?view=powershellsdk-7.6.0) | fact | `Parser.ParseInput` parses supplied text and returns tokens and parse errors without requiring the candidate command to be executed. CBH therefore uses the same parser channel to verify the translated PowerShell syntax. Its local subject extractor separately carries multiline quote, here-string, line-comment, and nested block-comment state before balanced-loop extraction. | Zero parse errors prove only parseability within the bound subject/profile. The local lexical masker is not the PowerShell parser and requires its own regressions. Neither mechanism proves runtime behavior, output correctness, permissions, or target correctness. |
| Python inline-write syntax extraction | Python Software Foundation, [`ast` — Abstract Syntax Trees](https://docs.python.org/3.12/library/ast.html) | fact | `ast.parse` parses Python source into an AST, and literal values and calls are represented by inspectable nodes. CBH uses this only to extract a narrow set of known inline write-call shapes, literal targets, constant payloads, and a payload-independent binding of interpreter options plus write API/mode/encoding/options without executing the candidate source. | AST parsing and narrow extraction do not prove that the command is executable, correct, free of other side effects, or fully classified. Opaque or compound operation envelopes fail closed; local implementation behavior still requires tests. |
| Bash heredoc expansion-preserving transport (reference only) | GNU Bash, [Redirections: Here Documents](https://www.gnu.org/software/bash/manual/html_node/Redirections.html) | fact | A quoted delimiter suppresses expansion of the here-document body, while an unquoted delimiter applies parameter expansion, command substitution, and arithmetic expansion. This informs the retained Bash reference adapter. | The current Windows/Git-Bash transport did not pass independent callability checks and is not an active supported surface. The manual does not validate the local matcher, transport, Bash availability, target binding, or runtime result. |
| Unicode replacement-character containment | Unicode Consortium, [Special Areas and Format Characters: U+FFFD](https://www.unicode.org/versions/Unicode16.0.0/core-spec/chapter-23/) | fact | U+FFFD is the general substitute character and can indicate an unknown/unmappable character or conversion error. CBH marks its propagation for predictive review on mechanically identified filesystem-content mutation surfaces and requires exact-target strict UTF-8 readback before retiring the task-local review; non-file message/email destinations are not treated as file paths. | U+FFFD may be intentional, and its absence does not prove that text is semantically correct or free of other mojibake. Source encoding/provenance still requires separate evidence. Other output surfaces need their own verifier profile rather than reusing file readback. |

## Migration rule

New recurrence classes should reuse the same lifecycle:

```text
identify executor/environment
-> classify the narrow invalid behavior
-> bind normalized subject and exact target when required
-> choose auto_rewrite / preflight_validate / predictive_review / no_match
-> bind the unchanged current candidate to source records and a verifier
-> rewrite only for an accepted deterministic profile; otherwise validate or review
-> verify the declared postcondition
-> calibrate and retire task-local state
```

Adding a profile must not expand action authorization, write long-term memory,
mutate policy automatically, or introduce a global token ban. Promotion remains
an offline evidence review using real historical failures and negative controls.
