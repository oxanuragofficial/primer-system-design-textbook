# Book source

The PDF is generated from Markdown chapters (`chapters/`), figure definitions (`figs/`, Graphviz `.dot`, sequence `.seq`, small Python/SVG generators), a stylesheet and a build script.

```bash
pip install weasyprint markdown pygments pypdf
sudo apt install graphviz            # provides `dot`
python build.py                      # full book -> out/book.pdf (create an empty out/ and cache/ folder first)
python build.py 23                   # one chapter -> out/part.pdf
python validate.py out/book.pdf      # automated checks -> out/validation.json
```
Fonts used: Bitstream Charter, Inter, DejaVu Sans Mono (install them, or edit `style.css`).
The code listings in chapter 30 are generated from `../code/` by `gen_oo.py` (`oo_template.md` is the template).
