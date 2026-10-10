# Tolerance test

One 10 mm peg and a plate with seven holes at per-side clearances from 0.05 to
0.40 mm (engraved under each hole). The holes are cut with the same `hole()`
helper the rest of the library uses, so the results map 1:1 onto the profile.

1. Print both parts in the material you care about (PLA and PETG differ).
2. Try the peg in each hole and note the tightest hole where it:
   - goes in with firm pressure → **press**
   - slides in and stays put → **snug**
   - turns freely → **slide**
3. Put those numbers in `tolerances:` in `printlib/profiles/kobra2plus.yaml`
   and rebuild any models with mating parts.

See [PRINT.md](PRINT.md) for generated print notes.
