"""DXF de exemplo em UTM 22S (SIRGAS 2000), perto da parcela da planilha SIGEF de teste.

Gerar o arquivo para testar na tela:
    .venv\\Scripts\\python.exe -m tests.exemplo_dxf
"""
import io
from pathlib import Path

import ezdxf

E0, N0 = 742_600.0, 6_945_300.0


def criar_exemplo() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2018", setup=True)
    doc.layers.add("VERTICES", color=1)                       # vermelho (ACI)
    doc.layers.add("DIVISA", color=2, lineweight=50)          # amarelo, 0,50 mm
    doc.layers.add("EDIFICACAO", color=4)                     # ciano
    doc.layers.add("TEXTOS", color=7)
    doc.layers.add("ARRUAMENTO", true_color=ezdxf.colors.rgb2int((255, 128, 0)))
    msp = doc.modelspace()

    cantos = [(E0, N0), (E0 + 60, N0), (E0 + 60, N0 + 40), (E0, N0 + 40)]
    for i, (x, y) in enumerate(cantos, start=1):
        msp.add_point((x, y, 10.0 + i), dxfattribs={"layer": "VERTICES"})
        msp.add_text(f"P{i}", height=1.0, dxfattribs={"layer": "TEXTOS"}) \
            .set_placement((x + 0.2, y + 0.2))
    # divisa fechada com um trecho em arco (bulge = 1 → semicírculo) entre P2 e P3
    msp.add_lwpolyline([(E0, N0, 0), (E0 + 60, N0, 1.0), (E0 + 60, N0 + 40, 0), (E0, N0 + 40, 0)],
                       format="xyb", close=True, dxfattribs={"layer": "DIVISA"})
    msp.add_line((E0 - 10, N0 - 5), (E0 + 90, N0 - 5), dxfattribs={"layer": "ARRUAMENTO"})
    msp.add_circle((E0 + 20, N0 + 20), 5, dxfattribs={"layer": "EDIFICACAO"})
    msp.add_arc((E0 + 40, N0 + 20), 5, 0, 90, dxfattribs={"layer": "EDIFICACAO", "color": 3})
    # arco espelhado (extrusão -Z): centro em OCS (-E, N) = WCS (E, N)
    msp.add_arc((-(E0 + 30), N0 + 10), 3, 0, 180,
                dxfattribs={"layer": "EDIFICACAO", "extrusion": (0, 0, -1)})
    h = msp.add_hatch(color=5, dxfattribs={"layer": "EDIFICACAO"})
    h.paths.add_polyline_path([(E0 + 5, N0 + 5), (E0 + 15, N0 + 5), (E0 + 15, N0 + 12),
                               (E0 + 5, N0 + 12)], is_closed=True)
    bloco = doc.blocks.new("MARCO")
    bloco.add_circle((0, 0), 0.3)
    bloco.add_attdef("NUM", (0.5, 0), dxfattribs={"height": 0.5})
    ins = msp.add_blockref("MARCO", (E0 + 30, N0 + 35), dxfattribs={"layer": "VERTICES"})
    ins.add_auto_attribs({"NUM": "M-01"})
    msp.add_mtext("Área de teste", dxfattribs={"layer": "TEXTOS", "insert": (E0 + 25, N0 + 30)})
    msp.add_point((0, 0), dxfattribs={"layer": "0"})           # objeto solto na origem
    return doc


def exemplo_bytes() -> bytes:
    buf = io.StringIO()
    criar_exemplo().write(buf)
    return buf.getvalue().encode("utf-8")


if __name__ == "__main__":
    destino = Path(__file__).parent / "dados" / "exemplo_utm22s.dxf"
    destino.write_bytes(exemplo_bytes())
    print(f"Gerado: {destino}")
