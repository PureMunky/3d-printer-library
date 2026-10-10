# Doll household accessories + gummy bears

One print plate of 1:6-scale home accessories for Barbie-size (~29 cm)
dolls, plus 8 little gummy bears. Every item is sized from the real object
÷ 6 and shaped to print without supports.

![household](preview-household.png)

![gummies](preview-gummies.png)

## What's included (29 pieces, two files)

| Kitchen | Home | Treats |
|---|---|---|
| 2 mugs (with handles) | open laptop (keyboard + screen detail) | 8 gummy bears (~10 mm) |
| 2 dinner plates | phone | |
| 2 bowls | TV remote | |
| frying pan | 3 books (different sizes) | |
| pot (with handles) + lid | wall clock | |
| toaster (two slots + lever) | trash can | |
| cutting board, spoon, spatula | | |

## Printing

- **`doll-house-accessories-household.stl`**: all 21 household items, about 2h 55m and 115 g of PLA.
- **`doll-house-accessories-gummies.stl`**: the 8 gummy bears, about 4 minutes and 1.5 g. Print
  them in translucent red, orange, green or yellow PLA/PETG so they look like real gummies.
- No supports on either.
- It's a plate of small parts, so a clean, well-levelled first layer matters
  most. Add a brim if small pieces lift.
- Want everything in one file instead? `--set split=false` packs it all on a single plate.
- Engraved details (phone screen, laptop keys, book pages, clock) stand out
  with a quick wash of acrylic paint.
- The gummy bears look like candy but are small plastic parts; keep them away
  from little kids.

## Parameters

| Param | Default | Notes |
|---|---|---|
| `scale` | 6 | real size ÷ scale. 6 = Barbie; 12 ≈ 1:12 dollhouse (check small parts) |
| `gummy_count` | 8 | |
| `gummy_height` | 10 | mm. 6 is about the smallest that still looks like a bear |
| `split` | true | separate household / gummies STLs; false = one combined plate |
| `plate_width` | 250 | packing width on the bed |

```bash
python -m printlib build doll-house-accessories --set gummy_count=12 --out scratch/more-gummies
python -m printlib bundle doll-house-accessories --name doll-house
```

See [PRINT.md](PRINT.md).
