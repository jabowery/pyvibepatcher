# ModSpec — DSL for Program Modification Directives (Two‑Level Specification)

This version clarifies the distinction between **syntax** (EBNF) and **semantics** (command schemas). It supersedes earlier drafts by introducing a resolver layer and removing deprecated Schema C.

---

## 1) Syntax Layer — Lexical Grammar (EBNF)
```
file        := { block }

block       := header nl block_body
header      := "MMM" ws ident ws "MMM"
ident       := letter { letter | digit | "_" }

block_body  := section { sep section } nlopt
section     := { line }
sep         := nl? "@@@@@@" nl?           # lines equal to "@@@@@@" after strip()

nl          := "\r\n" | "\n"
nlopt       := { nl }
ws          := " " { " " | "\t" }
line        := textline
textline    := ( "\\" "@@@@@@" ) | ( any_char_except_eol )*
```
Notes
- Defines only surface structure: how to split text into `MMM` blocks and `@@@@@@` sections.
- Does **not** assign meaning to sections; semantics is layered on top.

---

## 2) Semantics Layer — Command Registry & Schema Resolver
Each command name corresponds to a set of **schemas** (arity and pattern rules). The resolver maps raw sections → typed arguments using these schemas.

### Core file commands
| Command | Arity | Semantics |
|----------|--------|-----------|
| `modification_description` | 1 | Description text only |
| `create_file` | 2–3 | `(path, content, [make_executable])` |
| `replace_file_contents` | 2–3 | `(path, content, [make_executable])` |
| `move_file` | 2 | `(src, dst)` |
| `make_directory` | 1 | `(path)` |
| `remove_file` | 1–2 | `(path, [recursive])` |
| `update_header` | 1 | `(new_header_text)` |

### Code‑level commands (scope‑aware)
`dotted_target := name { "." name }`

#### declare
- **Schema A — Shorthand (2 sections)**  
  sections = `[combined, content]`
  - `combined` must match `^(.+?\.py)\.(.+)$`
  - Split at the **first** `.py` → `file_path = group1 + '.py'`, `dotted_target = group2`
  - `content` must be non‑empty.
  - Action → add/replace `dotted_target` in `file_path`.

- **Schema B — Explicit (3 sections)**  
  sections = `[file_path, dotted_target, content]`
  - `content` must be non‑empty.
  - Action → add/replace `dotted_target` in `file_path`.

*No legacy delete schema C exists.* Deletion must use `remove_declaration`.

#### update_declaration
- **Schema — (3 sections)** → `[file_path, dotted_target, content]`
  - `content` must be non‑empty.
  - Action → add/replace only (no delete).

#### remove_declaration
- **Schema — (2 sections)** → `[file_path, dotted_target]`
  - Must have exactly two sections (no content block).
  - Action → delete all matches of `dotted_target` in `file_path`.

### Resolver algorithm (deterministic)
1. Parse block → `(cmd_name, sections[])`.
2. Lookup schemas for `cmd_name` in priority order.
   - For `declare`: [Schema A, Schema B].
3. For each schema, check arity and validators (`regex`, non‑empty, etc.).
4. Use the first schema that validates; raise error otherwise.
5. Execute operation using lexical replacement rules:
   - Replace all matches of `dotted_target` in AST scope.
   - Preserve decorators and indentation.
   - If no match found, insert after header/imports and before `if __name__ == "__main__"`.

---

## 3) Boolean and Path Conventions
- Booleans accept: `true/false/yes/no/y/n/1/0` (case‑insensitive).
- Relative paths resolve from current working directory.
- `dotted_target` strictly matches `name(.name)*`.

---

## 4) Guardrails
- `update_declaration` rejects empty content.
- `remove_declaration` rejects extra sections.
- `declare` rejects empty content (legacy delete removed).
- Schema resolution is strict: no partial matches applied.

---

## 5) Attribute‑Grammar Perspective
```
Block(name, sections[]) → Cmd(name, Args)
Args := SchemaResolver(name, sections)
SchemaResolver checks:
  is_shorthand(s0) := regex("^(.+?\\.py)\\.(.+)$")
  nonempty(s) := len(s.strip()) > 0
  valid_target(t) := matches name(.name)*
```
This makes the syntax→semantics mapping explicit for testing and CI.

---

## 6) Example (Shorthand Form)
```
MMM declare MMM
src/foo/bar.py.baz_function
@@@@@@
def baz_function():
    return 42
```
→ Parsed as (file_path="src/foo/bar.py", dotted_target="baz_function", content = def block)

---

## 7) Validator Checklist (for CI)
- [ ] Known command name.
- [ ] Valid schema detected.
- [ ] Section count matches schema.
- [ ] Non‑empty content for declare/update.
- [ ] No content for remove.
- [ ] Valid `dotted_target`.
- [ ] Line endings/encoding preserved.

*End of two‑level specification.*

