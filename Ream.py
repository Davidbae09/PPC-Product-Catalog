"""
A1NE REAM PAPER - Blender script v3 (Blender 3.6 / 4.x)
-------------------------------------------------------
Dieline wrapper -> ream kertas 3D (lipatan di ATAS & BAWAH).

Garis hitam dieline (image.png, 732 x 503 px) yang dipakai sebagai acuan:
   vertikal  : x = 24 | 135 | 194 | 468 | 527 | 724
   horizontal: y = 57.5 (lipatan atas) | 446.5 (lipatan bawah)

   panel B 135-194  spine kiri (logo vertikal)
   panel C 194-468  muka DEPAN (kurva + logo)
   panel D 468-527  spine kanan
   panel E 527-724 + A 24-135  muka BELAKANG (E menimpa A)

Lipatan atas/bawah dibuat seperti bungkus ream asli:
   - flap berbentuk trapesium dengan sisi diagonal 45 derajat (sama dengan
     garis diagonal pada dieline)
   - flap muka depan berada PALING ATAS, flap belakang di bawahnya
   - spine dilipat jadi segitiga (tuck) masuk ke dalam, tertutup flap
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector, noise

# =============================================================
# 1. KONFIGURASI
# =============================================================
IMAGE_PATH = r"C:\users\lenovo\Downloads\image.png"     # <-- GANTI: file dieline wrapper
RENDER_NOW = True                         # True = langsung render & simpan
OUTPUT_PATH = r"C:\users\lenovo\Downloads\a1ne_render.png"

FRONT = "C"                 # "C" = muka kurva+logo (seperti contoh) | "F1" = muka upright (E+A)
TOP_TEXT_UPRIGHT = True     # True: tulisan di flap ATAS terbaca tegak dari depan (seperti contoh)
                            # False: orientasi asli dieline (tulisan terbalik dari depan)
BOTTOM_TEXT_UPRIGHT = True  # True: flap BAWAH dibuat sama seperti atas -> jika ream dibalik (bawah jadi atas,
                            #       muka depan tetap menghadap Anda) tulisan terbaca tegak.
                            # False: orientasi asli dieline (tegak jika dilihat dengan kamera
                            #       diputar ke bawah / Ctrl+Numpad7)

BACKDROP_IN_VIEWPORT = False   # False: backdrop/lantai disembunyikan di viewport (tetap ikut render) supaya
                               # ream bisa diperiksa dari bawah tanpa terhalang lantai

# --- pencahayaan & warna ---
LIGHT_SCALE = 1.0           # pengali semua lampu: render terlalu terang -> 0.7 | terlalu gelap -> 1.3
EXPOSURE = 0.0              # koreksi exposure akhir (stop). Terlalu terang: -0.5, terlalu gelap: +0.5
SATURATION = 1.12           # penguat warna cetakan (merah lebih kaya)
DARK_RED_DEEPEN = 0.65      # 1.0 = merah tua dieline apa adanya | 0.65 = lebih pekat seperti foto referensi

# --- kamera: dicocokkan dengan foto referensi (3/4 dari kiri-depan, sedikit dari atas, lensa tele) ---
CAM_LENS = 200              # mm. Lensa tele -> perspektif datar seperti foto produk. Lebih kecil = perspektif lebih kuat
CAM_DISTANCE = None         # None = otomatis (ream mengisi frame sesuai CAM_FRAME_FILL). Isi angka (m) untuk manual
CAM_FRAME_FILL = 0.94       # tinggi ream (termasuk permukaan atas) = 94% tinggi frame, seperti foto referensi
CAM_AZIMUTH = 32            # derajat putar ke kiri dari muka depan (makin besar = spine kiri makin lebar)
CAM_ELEVATION = 17          # derajat di atas horizontal (makin besar = permukaan atas makin terlihat)
CAM_FSTOP = 16              # makin besar = makin tajam dari depan sampai belakang
CAM_SHIFT_Y = 0.0           # koreksi framing vertikal tambahan (framing sudah otomatis di tengah)

# --- kalibrasi pencahayaan otomatis ---
AUTO_CALIBRATE = True       # render uji kecil -> terang muka depan/spine/latar disamakan dengan foto referensi
TARGET_FRONT_RED = 222      # nilai R (0-255) merah terang muka depan pada foto referensi
TARGET_SPINE_R = 82         # nilai R spine kiri (lebih gelap dari muka depan)
TARGET_BG = 228             # abu latar rata-rata (kiri 224 -> kanan 232)

# --- efek lipatan overlapping (flap menimpa segitiga lipatan samping, seperti contoh) ---
FOLD_DEPTH = 1.0            # kedalaman lipatan: 0.5 = tipis | 1.0 = sedang | 1.6 = tegas (segitiga makin masuk)
FOLD_AO = 0.85              # kekuatan bayangan kontak di bawah tepi flap (0 = mati, 1 = penuh)
FOLD_AO_DISTANCE = 0.008    # jangkauan bayangan kontak (meter)
FOLD_GRADIENT = 0.80        # gradasi gelap pada segitiga lipatan (makin gelap ke ujung) & tepi flap. 0 = mati, 1 = penuh

# --- ketajaman tekstur ---
UPSCALE = 3                 # perbesar dieline kecil hingga x3 (otomatis dibatasi maks. ~3600 px lebar)
SHARPEN = 1.1               # kekuatan unsharp mask (0 = nonaktif)
HIRES_WIDTH = 2800          # dieline selebar ini atau lebih = resolusi tinggi -> dipakai apa adanya
SHARPEN_MAX_PIXELS = 8_000_000   # batas ukuran gambar untuk penajaman (hemat memori)

# --- kualitas ---
RENDER_SAMPLES = 256
RES_X, RES_Y = 2304, 1536     # rasio 3:2 seperti foto referensi
WRINKLE = 0.0007            # kedalaman kerutan kertas (meter), 0 = tanpa kerutan
PILLOW = 0.0028             # kegemukan wrapper

REF_W, REF_H = 732, 503
X_GLUE, X_A1, X_B1, X_C1, X_D1, X_E1 = 24, 135, 194, 468, 527, 724
Y_TOP, Y_BOT = 57.5, 446.5
IN = 1.5

PANELS = {
    "B":  [(X_A1 + IN, X_B1 - IN)],
    "C":  [(X_B1 + IN, X_C1 - IN)],
    "D":  [(X_C1 + IN, X_D1 - IN)],
    "F1": [(X_D1 + IN, X_E1 - IN), (58, X_A1 - IN)],
}
SEQ = ["F1", "B", "C", "D"]

TOP_STRIP = (Y_TOP - IN, 6)          # (engsel, tepi luar) pada dieline
BOT_STRIP = (Y_BOT + IN, 500)

# titik polos (tanpa teks) pada strip flap tiap panel -> dipakai untuk penutup ujung ream
PLAIN = {"B": (164, 28), "C": (203, 22), "D": (497, 28), "F1": (600, 28)}

W = 0.210
K = W / (X_C1 - X_B1)                # meter per px
T = (X_B1 - X_A1) * K                # tebal ream
H = (Y_BOT - Y_TOP) * K              # tinggi ream
CAP_DROP = 0.0015 + 0.004 * FOLD_DEPTH   # kedalaman penutup ujung (di bawah segitiga lipatan)
LIFT = 0.003                         # ream diangkat 3 mm dari lantai (flap bawah tidak menembus lantai)

# =============================================================
# 2. RESET SCENE
# =============================================================
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
    for item in list(coll):
        if item.users == 0:
            coll.remove(item)

scene = bpy.context.scene
STATE = {}          # objek yang dipakai kalibrasi (lampu, emisi latar, kamera)


def link(obj):
    scene.collection.objects.link(obj)
    return obj


# =============================================================
# 3. UTILITAS
# =============================================================
def px(x, y):
    return Vector((x / REF_W, 1.0 - y / REF_H))


def set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def wrinkle_offset(pos, weight):
    """Kerutan halus kertas (noise berlapis)."""
    if WRINKLE <= 0 or weight <= 0:
        return 0.0
    n1 = noise.noise(pos * 38.0)
    n2 = noise.noise(pos * 95.0 + Vector((7.1, 3.3, 1.9)))
    n3 = noise.noise(pos * 230.0 + Vector((2.2, 9.4, 5.5)))
    return WRINKLE * weight * (0.6 * n1 + 0.3 * n2 + 0.1 * n3)


def add_grid(bm, uvl, origin, uvec, vvec, normal, rect, nu=14, nv=14,
             bulge=0.0, sfull=(0.0, 1.0)):
    """rect=(x_s0, y_t0, x_s1, y_t1) px. sfull = bagian s terhadap seluruh muka."""
    xl, yb, xr, yt = rect
    a, b, c = px(xl, yb), px(xr, yb), px(xl, yt)
    nrm = Vector(normal).normalized()
    verts, uvs = [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            s, t = i / nu, j / nv
            S = sfull[0] + s * (sfull[1] - sfull[0])
            env = (math.sin(math.pi * S) * math.sin(math.pi * t)) ** 0.8
            edge = min(S, 1 - S, t, 1 - t)
            wgt = min(1.0, edge / 0.06)                    # nol di tepi -> tidak ada celah
            base = origin + uvec * s + vvec * t
            pos = base + nrm * (bulge * env + wrinkle_offset(base, wgt * (0.35 + 0.65 * (1 - env))))
            verts.append(bm.verts.new(pos))
            uvs.append(a + (b - a) * s + (c - a) * t)
    flip = uvec.cross(vvec).dot(nrm) < 0
    for j in range(nv):
        for i in range(nu):
            idx = [j * (nu + 1) + i, j * (nu + 1) + i + 1,
                   (j + 1) * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i]
            if flip:
                idx.reverse()
            try:
                f = bm.faces.new([verts[k] for k in idx])
            except ValueError:
                continue
            for loop, k in zip(f.loops, idx):
                loop[uvl].uv = uvs[k]


def add_tri(bm, uvl, pts, uvs, normal, shades=None):
    vs = [bm.verts.new(p) for p in pts]
    if shades is not None and STATE.get("shade") is not None:
        for v_, sh_ in zip(vs, shades):
            v_[STATE["shade"]] = sh_
    order = [0, 1, 2]
    if (pts[1] - pts[0]).cross(pts[2] - pts[0]).dot(Vector(normal)) < 0:
        order = [0, 2, 1]
    f = bm.faces.new([vs[k] for k in order])
    for loop, k in zip(f.loops, order):
        loop[uvl].uv = uvs[k]


# =============================================================
# 4. MATERIAL
# =============================================================
def load_image():
    if not os.path.exists(IMAGE_PATH):
        raise FileNotFoundError(f"Gambar dieline tidak ditemukan: {IMAGE_PATH}\n"
                                "Ubah IMAGE_PATH di bagian atas script.")
    img = bpy.data.images.load(IMAGE_PATH, check_existing=True)
    img.reload()          # selalu mulai dari file asli di disk
    prepare_texture(img)
    return img


def prepare_texture(img):
    """
    Penyesuaian tekstur otomatis menurut resolusi dieline:
      - dieline kecil (< ~1800 px)  : diperbesar (maks. ~3600 px) lalu dipertajam
      - dieline sedang               : dipertajam saja bila memori aman
      - dieline resolusi tinggi      : dipakai apa adanya (sudah tajam, hemat memori)
    """
    w, h = img.size
    print(f"Dieline: {w} x {h} px")
    if w >= HIRES_WIDTH:
        print("Resolusi tinggi -> tanpa upscale/penajaman (dipakai apa adanya).")
        return
    try:
        import numpy as np
    except ImportError:
        print("numpy tidak tersedia, lewati penajaman tekstur")
        return

    factor = max(1, min(UPSCALE, 3600 // max(w, 1)))
    if factor > 1:
        img.scale(w * factor, h * factor)
        w, h = img.size
    if SHARPEN <= 0:
        return
    if w * h > SHARPEN_MAX_PIXELS:
        print("Gambar terlalu besar untuk penajaman -> dilewati.")
        return

    try:
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        a = buf.reshape(h, w, 4)
        rgb = a[..., :3].copy()

        sigma = 0.55 * max(1, factor)
        rad = int(math.ceil(sigma * 2.5))
        xs = np.arange(-rad, rad + 1, dtype=np.float32)
        ker = np.exp(-(xs ** 2) / (2 * sigma ** 2))
        ker /= ker.sum()

        def blur(x):
            pad = np.pad(x, ((rad, rad), (0, 0), (0, 0)), mode="edge")
            y = sum(ker[i] * pad[i:i + x.shape[0]] for i in range(len(ker)))
            pad = np.pad(y, ((0, 0), (rad, rad), (0, 0)), mode="edge")
            return sum(ker[i] * pad[:, i:i + x.shape[1]] for i in range(len(ker)))

        a[..., :3] = np.clip(rgb + SHARPEN * (rgb - blur(rgb)), 0.0, 1.0)
        img.pixels.foreach_set(a.ravel())
        img.update()
    except MemoryError:
        print("Memori tidak cukup untuk penajaman -> dilewati (tekstur tetap dipakai).")


def make_wrapper_material(img):
    mat = bpy.data.materials.new("A1ne_Wrapper")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new

    out = N("ShaderNodeOutputMaterial")
    bsdf = N("ShaderNodeBsdfPrincipled")
    tex = N("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"

    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.35)
    set_input(bsdf, ["Coat Weight", "Clearcoat"], 0.08)           # satin, tidak berkabut
    set_input(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.2)
    set_input(bsdf, ["Subsurface Weight", "Subsurface"], 0.0)
    set_input(bsdf, ["Sheen Weight", "Sheen"], 0.0)

    coord = N("ShaderNodeTexCoord")

    # Roughness bervariasi (cetakan glossy tidak seragam)
    n_rough = N("ShaderNodeTexNoise")
    n_rough.inputs["Scale"].default_value = 25.0
    n_rough.inputs["Detail"].default_value = 6.0
    ramp = N("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.38, 0.38, 0.38, 1)
    ramp.color_ramp.elements[1].position = 0.65
    ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.55, 1)
    L(coord.outputs["Object"], n_rough.inputs["Vector"])
    L(n_rough.outputs["Fac"], ramp.inputs["Fac"])
    L(ramp.outputs["Color"], bsdf.inputs["Roughness"])

    # Bump: serat kertas (halus) + gelombang lebar
    n_fiber = N("ShaderNodeTexNoise")
    n_fiber.inputs["Scale"].default_value = 420.0
    n_fiber.inputs["Detail"].default_value = 10.0
    n_wave = N("ShaderNodeTexNoise")
    n_wave.inputs["Scale"].default_value = 12.0
    n_wave.inputs["Detail"].default_value = 4.0
    b_wave = N("ShaderNodeBump")
    b_wave.inputs["Strength"].default_value = 0.08
    b_wave.inputs["Distance"].default_value = 0.002
    b_fiber = N("ShaderNodeBump")
    b_fiber.inputs["Strength"].default_value = 0.05
    b_fiber.inputs["Distance"].default_value = 0.0003
    L(coord.outputs["Object"], n_fiber.inputs["Vector"])
    L(coord.outputs["Object"], n_wave.inputs["Vector"])
    L(n_wave.outputs["Fac"], b_wave.inputs["Height"])
    L(b_wave.outputs["Normal"], b_fiber.inputs["Normal"])
    L(n_fiber.outputs["Fac"], b_fiber.inputs["Height"])
    L(b_fiber.outputs["Normal"], bsdf.inputs["Normal"])

    hsv = N("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = SATURATION
    color_src = tex.outputs["Color"]
    try:
        # Mask area merah tua: R sedang, G & B rendah (merah terang, emas, putih tidak terkena)
        sep = N("ShaderNodeSeparateColor")
        L(tex.outputs["Color"], sep.inputs["Color"])
        mg = N("ShaderNodeMapRange")
        mg.inputs["From Min"].default_value = 0.04
        mg.inputs["From Max"].default_value = 0.10
        mg.inputs["To Min"].default_value = 1.0
        mg.inputs["To Max"].default_value = 0.0
        L(sep.outputs["Green"], mg.inputs["Value"])
        mr = N("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.50
        mr.inputs["From Max"].default_value = 0.68
        mr.inputs["To Min"].default_value = 1.0
        mr.inputs["To Max"].default_value = 0.0
        L(sep.outputs["Red"], mr.inputs["Value"])
        mask = N("ShaderNodeMath")
        mask.operation = "MULTIPLY"
        L(mg.outputs["Result"], mask.inputs[0])
        L(mr.outputs["Result"], mask.inputs[1])
        deepen = N("ShaderNodeMixRGB")
        deepen.blend_type = "MULTIPLY"
        deepen.inputs["Color2"].default_value = (DARK_RED_DEEPEN, DARK_RED_DEEPEN, DARK_RED_DEEPEN, 1)
        L(mask.outputs["Value"], deepen.inputs["Fac"])
        L(tex.outputs["Color"], deepen.inputs["Color1"])
        color_src = deepen.outputs["Color"]
    except Exception as e:
        print("Pendalaman merah tua dilewati:", e)
    L(color_src, hsv.inputs["Color"])
    final_color = hsv.outputs["Color"]
    try:
        # Bayangan kontak lokal: tepi flap yang menimpa segitiga lipatan -> bagian bawahnya gelap bergradasi
        ao = N("ShaderNodeAmbientOcclusion")
        ao.inputs["Distance"].default_value = FOLD_AO_DISTANCE
        ao.only_local = True
        ao.samples = 16
        L(hsv.outputs["Color"], ao.inputs["Color"])
        mix_ao = N("ShaderNodeMixRGB")
        mix_ao.blend_type = "MIX"
        mix_ao.inputs["Fac"].default_value = FOLD_AO
        L(hsv.outputs["Color"], mix_ao.inputs["Color1"])
        L(ao.outputs["Color"], mix_ao.inputs["Color2"])
        final_color = mix_ao.outputs["Color"]
    except Exception as e:
        print("Bayangan kontak lipatan dilewati:", e)
    try:
        # Gradasi lipatan: warna dikalikan nada gelap sesuai atribut "fold_shade" (0 = normal, 1 = paling gelap)
        attr = N("ShaderNodeAttribute")
        attr.attribute_type = "GEOMETRY"
        attr.attribute_name = "fold_shade"
        gfac = N("ShaderNodeMath")
        gfac.operation = "MULTIPLY"
        gfac.use_clamp = True
        gfac.inputs[1].default_value = FOLD_GRADIENT
        L(attr.outputs["Fac"], gfac.inputs[0])
        darker = N("ShaderNodeMixRGB")
        darker.blend_type = "MULTIPLY"
        darker.inputs["Fac"].default_value = 1.0
        darker.inputs["Color2"].default_value = (0.30, 0.26, 0.27, 1.0)
        L(final_color, darker.inputs["Color1"])
        mix_g = N("ShaderNodeMixRGB")
        mix_g.blend_type = "MIX"
        L(gfac.outputs["Value"], mix_g.inputs["Fac"])
        L(final_color, mix_g.inputs["Color1"])
        L(darker.outputs["Color"], mix_g.inputs["Color2"])
        final_color = mix_g.outputs["Color"]
    except Exception as e:
        print("Gradasi lipatan dilewati:", e)
    L(final_color, bsdf.inputs["Base Color"])
    L(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_simple_material(name, color, rough):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


# =============================================================
# 5. MODEL REAM + WRAPPER
# =============================================================
def build_wrapper(mat):
    mesh = bpy.data.meshes.new("A1ne_Wrapper_Mesh")
    obj = link(bpy.data.objects.new("A1ne_Wrapper", mesh))
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    shade_layer = bm.verts.layers.float.new("fold_shade")   # gradasi lipatan (dibaca material)
    STATE["shade"] = shade_layer
    hw, ht, hh = W / 2, T / 2, H / 2

    k = SEQ.index(FRONT)
    order = SEQ[k:] + SEQ[:k]
    slot = dict(zip(["front", "spine_R", "back", "spine_L"], order))

    # origin, arah s, normal, panjang, arah ke dalam (menuju tengah ujung ream)
    geo = {
        "front":   (Vector((-hw, -ht, 0)), Vector((1, 0, 0)),  (0, -1, 0), W, Vector((0, 1, 0))),
        "spine_R": (Vector((hw, -ht, 0)),  Vector((0, 1, 0)),  (1, 0, 0),  T, Vector((-1, 0, 0))),
        "back":    (Vector((hw, ht, 0)),   Vector((-1, 0, 0)), (0, 1, 0),  W, Vector((0, -1, 0))),
        "spine_L": (Vector((-hw, ht, 0)),  Vector((0, -1, 0)), (-1, 0, 0), T, Vector((1, 0, 0))),
    }

    def seg_widths(panel, total):
        segs = PANELS[panel]
        pxw = [s[1] - s[0] for s in segs]
        return segs, [total * p / sum(pxw) for p in pxw]

    # ---------- badan ----------
    for side, panel in slot.items():
        origin, udir, normal, total, inward = geo[side]
        segs, widths = seg_widths(panel, total)
        is_spine = side.startswith("spine")
        off = 0.0
        for (x0, x1), w in zip(segs, widths):
            nu = max(6, round((10 if is_spine else 52) * w / total))
            add_grid(bm, uvl, origin + udir * off + Vector((0, 0, -hh)),
                     udir * w, Vector((0, 0, H)), normal,
                     (x0, Y_BOT - IN, x1, Y_TOP + IN),
                     nu=nu, nv=70, bulge=PILLOW * (0.55 if is_spine else 1.0),
                     sfull=(off / total, (off + w) / total))
            off += w

    # ---------- flap trapesium atas & bawah ----------
    def add_flap(side, sg, strip, lift, rotate_uv):
        origin, udir, normal, total, inward = geo[side]
        segs, widths = seg_widths(slot[side], total)
        h0, h1 = strip
        strip_m = abs(h1 - h0) * K
        Lf = min(strip_m, T * 0.88)              # panjang flap = seluruh strip (diagonal 45 derajat)
        nu, nv = 14, 14
        off = 0.0
        for (x0, x1), w in zip(segs, widths):
            a, b = off, off + w
            rows = []
            for j in range(nv + 1):
                t = j / nv
                ins = Lf * t                      # sisi diagonal 45 derajat
                lo, hi = max(a, ins), min(b, total - ins)
                row = []
                for i in range(nu + 1):
                    s = lo + (hi - lo) * i / nu
                    X = x0 + (s - a) / w * (x1 - x0)
                    Y = h0 + (h1 - h0) * (t * Lf / strip_m)
                    if rotate_uv:
                        X, Y = x0 + x1 - X, h0 + h1 - Y
                    z = sg * (hh + lift * min(1.0, t * 5.0) + 0.0012 * math.sin(math.pi * t))
                    base = origin + udir * s + inward * (Lf * t) + Vector((0, 0, z))
                    pos = base + Vector((0, 0, sg * wrinkle_offset(base, 0.5) * 0.6))
                    nv_ = bm.verts.new(pos)
                    d_edge = min(s - ins, (total - ins) - s)                 # jarak ke tepi diagonal
                    fall = max(0.0, 1.0 - d_edge / (0.45 * Lf))              # 1 di tepi -> 0 di tengah
                    ramp_t = min(1.0, t * 4.0)                               # 0 di engsel (menyatu dengan badan)
                    nv_[shade_layer] = min(1.0, 0.65 * fall * ramp_t + 0.12 * t)
                    row.append((nv_, px(X, Y)))
                rows.append(row)
            for j in range(nv):
                for i in range(nu):
                    quad = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
                    p = [q[0].co for q in quad]
                    if (p[1] - p[0]).cross(p[3] - p[0]).z * sg < 0:
                        quad.reverse()
                    try:
                        f = bm.faces.new([q[0] for q in quad])
                    except ValueError:
                        continue
                    for loop, q in zip(f.loops, quad):
                        loop[uvl].uv = q[1]
            off += w

    # ---------- tuck segitiga pada spine ----------
    def add_tuck(side, sg, strip):
        origin, udir, normal, total, inward = geo[side]
        x0, x1 = PANELS[slot[side]][0]
        h0, h1 = strip
        strip_m = abs(h1 - h0) * K
        z0 = sg * hh
        p0 = origin + Vector((0, 0, z0))
        p1 = p0 + udir * T
        apex = p0 + udir * (T / 2) + inward * (T / 2) + Vector((0, 0, -sg * 0.004 * FOLD_DEPTH))  # ujung segitiga masuk ke dalam, ditimpa flap
        add_tri(bm, uvl, [p0, p1, apex],
                [px(x0, h0), px(x1, h0),
                 px((x0 + x1) / 2, h0 + (h1 - h0) * min(1.0, (T / 2) / strip_m))],
                (0, 0, sg), shades=[0.0, 0.0, 1.0])

    def add_cap(sg):
        """Penutup ujung ream: tidak ada celah -> bagian putih/kertas dalam tidak pernah terlihat."""
        z = sg * (hh - CAP_DROP)
        parts = [
            (-hw, T / 2, PLAIN[slot["spine_L"]]),
            (-hw + T / 2, W - T, PLAIN[slot["back"]]),
            (hw - T / 2, T / 2, PLAIN[slot["spine_R"]]),
        ]
        for x_start, width, (cx, cy) in parts:
            add_grid(bm, uvl, Vector((x_start, -ht, z)), Vector((width, 0, 0)),
                     Vector((0, T, 0)), (0, 0, sg),
                     (cx - 3, cy + 3, cx + 3, cy - 3), nu=2, nv=2)

    for sg, strip in ((1, TOP_STRIP), (-1, BOT_STRIP)):
        rot = TOP_TEXT_UPRIGHT if sg == 1 else BOTTOM_TEXT_UPRIGHT
        add_cap(sg)
        add_flap("back", sg, strip, 0.0008 * max(0.5, FOLD_DEPTH), rot)    # flap belakang (lapis tengah)
        add_flap("front", sg, strip, 0.0018 * max(0.5, FOLD_DEPTH), rot)   # flap depan (lapis paling atas)
        add_tuck("spine_L", sg, strip)
        add_tuck("spine_R", sg, strip)

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.update()

    sol = obj.modifiers.new("Thickness", "SOLIDIFY")   # kertas punya ketebalan -> tidak tembus pandang
    sol.thickness = 0.0006
    sol.offset = 0.0
    sol.use_even_offset = True

    bev = obj.modifiers.new("Bevel", "BEVEL")
    bev.width = 0.0010
    bev.segments = 3
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(40)

    obj.data.materials.append(mat)
    obj.location.z = hh + LIFT
    mat.use_backface_culling = False
    return obj


def build_paper_block():
    """Isi ream. Dibuat MERAH (bukan putih) + pelat penutup padat di kedua ujung,
    sehingga dari sudut mana pun (termasuk dari bawah) tidak ada bagian putih yang terlihat."""
    inner = make_simple_material("Ream_Inner", (0.55, 0.06, 0.05), 0.6)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, H / 2 + LIFT))
    blk = bpy.context.active_object
    blk.name = "Paper_Block"
    blk.scale = (W - 0.008, T - 0.008, H - 2 * (CAP_DROP + 0.003))
    blk.data.materials.append(inner)

    for sg, nm in ((1, "End_Plate_Top"), (-1, "End_Plate_Bottom")):
        z = LIFT + H / 2 + sg * (H / 2 - CAP_DROP - 0.0012)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z))
        pl = bpy.context.active_object
        pl.name = nm
        pl.scale = (W - 0.001, T - 0.001, 0.0016)
        pl.data.materials.append(inner)
    return blk


# =============================================================
# 6. STUDIO
# =============================================================
def build_backdrop():
    mesh = bpy.data.meshes.new("Backdrop_Mesh")
    obj = link(bpy.data.objects.new("Backdrop", mesh))
    prof = [(-4.0 + k * 0.55, 0.0) for k in range(0, 11)]
    r = 1.0
    for k in range(1, 13):
        a = math.radians(90 * k / 12)
        prof.append((1.5 + r * math.sin(a), r - r * math.cos(a)))
    for k in range(1, 5):
        prof.append((2.5, r + k * 0.8))
    xs = [-6, -3, 0, 3, 6]
    bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for x in xs] for (y, z) in prof]
    for i in range(len(rows) - 1):
        for j in range(len(xs) - 1):
            bm.faces.new([rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    bmat = make_simple_material("Backdrop_Mat", (0.04, 0.04, 0.045), 0.9)
    bnt = bmat.node_tree
    bb = bnt.nodes["Principled BSDF"]
    set_input(bb, ["Specular IOR Level", "Specular"], 0.0)       # tidak memantulkan softbox
    # Emisi berbasis koordinat layar -> latar abu high-key rata, tidak bergantung kuat lampu
    wcoord = bnt.nodes.new("ShaderNodeTexCoord")
    wsep = bnt.nodes.new("ShaderNodeSeparateXYZ")
    wramp = bnt.nodes.new("ShaderNodeValToRGB")
    wramp.color_ramp.elements[0].color = (0.72, 0.72, 0.735, 1)   # kiri  (~sRGB 221)
    wramp.color_ramp.elements[1].color = (0.84, 0.84, 0.85, 1)    # kanan (~sRGB 236)
    bnt.links.new(wcoord.outputs["Window"], wsep.inputs["Vector"])
    bnt.links.new(wsep.outputs["X"], wramp.inputs["Fac"])
    em_col = bb.inputs.get("Emission Color") or bb.inputs.get("Emission")
    bnt.links.new(wramp.outputs["Color"], em_col)
    set_input(bb, ["Emission Strength"], 1.0)
    STATE["bg_emission"] = bb.inputs["Emission Strength"]
    obj.data.materials.append(bmat)
    if obj.data.polygons[0].normal.z < 0:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def add_area(name, loc, size, energy, target, color=(1, 1, 1), ratio=0.7):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = "RECTANGLE"
    data.size = size
    data.size_y = size * ratio
    data.energy = energy
    data.color = color
    obj = link(bpy.data.objects.new(name, data))
    obj.location = loc
    c = obj.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return obj


def _cam_basis(az, el, dist):
    c = Vector((0, 0, H / 2 + LIFT))
    pos = c + Vector((-dist * math.cos(el) * math.sin(az),
                      -dist * math.cos(el) * math.cos(az),
                      dist * math.sin(el)))
    fw = (c - pos).normalized()
    right = fw.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fw)
    return pos, fw, right, up


def project_point(p, basis, shift=(0.0, 0.0)):
    """Titik 3D -> koordinat piksel render (x ke kanan, y ke bawah)."""
    pos, fw, right, up = basis
    f_px = CAM_LENS * RES_X / 36.0
    v = Vector(p) - pos
    z = v.dot(fw)
    return (RES_X / 2 + f_px * v.dot(right) / z - shift[0] * RES_X,
            RES_Y / 2 - f_px * v.dot(up) / z + shift[1] * RES_X)


def frame_camera():
    """Jarak kamera & shift otomatis: ream mengisi CAM_FRAME_FILL tinggi frame dan berada tepat di tengah."""
    az, el = math.radians(CAM_AZIMUTH), math.radians(CAM_ELEVATION)
    corners = [(x, y, z) for x in (-W / 2, W / 2) for y in (-T / 2, T / 2) for z in (LIFT, LIFT + H)]

    def extent(d):
        b = _cam_basis(az, el, d)
        pts = [project_point(c, b) for c in corners]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), max(xs), min(ys), max(ys)

    if CAM_DISTANCE:
        dist = CAM_DISTANCE
    else:
        lo, hi = 0.3, 30.0
        for _ in range(60):
            d = (lo + hi) / 2
            x0, x1, y0, y1 = extent(d)
            if (y1 - y0) > CAM_FRAME_FILL * RES_Y:
                lo = d
            else:
                hi = d
        dist = (lo + hi) / 2
    x0, x1, y0, y1 = extent(dist)
    sx = ((x0 + x1) / 2 - RES_X / 2) / RES_X
    sy = -((y0 + y1) / 2 - RES_Y / 2) / RES_X + CAM_SHIFT_Y
    return dist, sx, sy


def build_studio():
    target = link(bpy.data.objects.new("Focus_Target", None))
    target.location = (0, 0, H / 2 + LIFT)

    ls = LIGHT_SCALE
    # Pencahayaan studio lembut seperti foto referensi: muka depan rata & terang, spine kiri lebih gelap.
    # Key: softbox besar KANAN-depan (menerangi muka depan, tidak menyentuh spine kiri)
    key = add_area("Key_Softbox", (0.9, -1.6, 0.9), 2.0, 275 * ls, target, (1.0, 0.98, 0.95), 0.9)
    # Fill: dari KIRI-depan, rendah -> mengangkat spine kiri agar tidak hitam
    fill = add_area("Fill_Light", (-1.3, -1.1, 0.45), 1.6, 145 * ls, target, (0.94, 0.96, 1.0), 1.0)
    # Softbox atas: permukaan atas + lipatan
    top = add_area("Top_Softbox", (0.0, -0.4, 1.5), 1.2, 80 * ls, target, (1, 1, 1), 1.0)
    # Strip tepi halus (garis cahaya di sudut)
    rim_r = add_area("Rim_Right", (1.2, 0.8, 0.6), 0.35, 25 * ls, target, (1, 1, 1), 4.0)
    rim_l = add_area("Rim_Left", (-1.2, 0.6, 0.5), 0.35, 20 * ls, target, (1, 0.97, 0.94), 4.0)
    STATE["groups"] = {"key": [key, top, rim_r], "fill": [fill, rim_l]}

    dist, sx, sy = frame_camera()
    az, el = math.radians(CAM_AZIMUTH), math.radians(CAM_ELEVATION)
    pos, fw, right, up = _cam_basis(az, el, dist)
    print(f"Kamera: lensa {CAM_LENS} mm, jarak {dist:.2f} m, azimut {CAM_AZIMUTH}, elevasi {CAM_ELEVATION}")

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = CAM_LENS
    cam_data.sensor_width = 36
    cam_data.shift_x = sx
    cam_data.shift_y = sy
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = CAM_FSTOP
    cam = link(bpy.data.objects.new("Camera", cam_data))
    cam.location = pos
    c = cam.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    scene.camera = cam
    STATE["basis"] = (pos, fw, right, up)
    STATE["shift"] = (sx, sy)

    world = bpy.data.worlds.new("Studio_World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.82, 0.83, 0.86, 1)
    bg.inputs["Strength"].default_value = 0.15
    scene.world = world


# ---------- kalibrasi pencahayaan otomatis ----------
def _srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _probe_render():
    """Render uji kecil, kembalikan fungsi sample(x_frac, y_frac_dari_atas) -> (R, G, B) 0..1 (sRGB tampilan)."""
    import tempfile
    import numpy as np
    r, cy = scene.render, scene.cycles
    saved = (r.resolution_percentage, cy.samples, cy.use_denoising, cy.use_adaptive_sampling)
    r.resolution_percentage, cy.samples, cy.use_denoising, cy.use_adaptive_sampling = 12, 24, False, False
    try:
        bpy.ops.render.render(write_still=False)
        path = os.path.join(tempfile.gettempdir(), "a1ne_probe.png")
        bpy.data.images["Render Result"].save_render(path)
    finally:
        r.resolution_percentage, cy.samples, cy.use_denoising, cy.use_adaptive_sampling = saved
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4)

    def sample(xf, yf):
        x = min(w - 2, max(1, int(xf * w)))
        row = min(h - 2, max(1, h - 1 - int(yf * h)))      # baris 0 = bawah
        return a[row - 1:row + 2, x - 1:x + 2, :3].reshape(-1, 3).mean(0)

    result = sample
    bpy.data.images.remove(img)
    return result, (w, h)


def calibrate_lighting():
    """Samakan terang muka depan, spine, dan latar dengan foto referensi lewat render uji kecil."""
    if FRONT != "C":
        print("Kalibrasi otomatis hanya untuk FRONT = 'C' -> dilewati.")
        return
    basis, shift = STATE["basis"], STATE["shift"]
    # titik uji pada dieline: merah terang muka depan (417,391) dan spine kiri polos (165,217)
    def frac(px_, py_, x0, x1):
        return (px_ - x0) / (x1 - x0), (py_ - (Y_TOP + IN)) / ((Y_BOT - IN) - (Y_TOP + IN))
    uf, vf = frac(417, 391, *PANELS["C"][0])
    us, vs = frac(165, 217, *PANELS["B"][0])
    p_front = (-W / 2 + uf * W, -T / 2 - PILLOW * 0.9, LIFT + H * (1 - vf))
    p_spine = (-W / 2 - PILLOW * 0.5, T / 2 - us * T, LIFT + H * (1 - vs))
    sf = project_point(p_front, basis, shift)
    ss = project_point(p_spine, basis, shift)
    print(f"Titik uji (px): depan {sf[0]:.0f},{sf[1]:.0f}  spine {ss[0]:.0f},{ss[1]:.0f}")

    for it in range(3):
        sample, _ = _probe_render()
        front = sample(sf[0] / RES_X, sf[1] / RES_Y)[0]
        spine = sample(ss[0] / RES_X, ss[1] / RES_Y)[0]
        bgl, bgr = sample(0.04, 0.5)[0], sample(0.96, 0.5)[0]
        print(f"  iterasi {it + 1}: depan R={front*255:.0f} (target {TARGET_FRONT_RED}), "
              f"spine R={spine*255:.0f} (target {TARGET_SPINE_R}), latar={(bgl+bgr)*127.5:.0f} (target {TARGET_BG})")

        def gain(meas, tgt):
            g = _srgb_to_lin(tgt / 255.0) / max(1e-4, _srgb_to_lin(max(meas, 1e-3)))
            return min(2.0, max(0.5, g))

        g_key = gain(front, TARGET_FRONT_RED)
        g_fill = gain(spine, TARGET_SPINE_R)
        g_bg = gain((bgl + bgr) / 2, TARGET_BG)
        for l in STATE["groups"]["key"]:
            l.data.energy *= g_key
        for l in STATE["groups"]["fill"]:
            l.data.energy *= g_fill
        STATE["bg_emission"].default_value *= g_bg
        if abs(g_key - 1) < 0.03 and abs(g_fill - 1) < 0.05 and abs(g_bg - 1) < 0.03:
            break
    print("Kalibrasi selesai.")


def enable_gpu():
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev_type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = dev_type
                prefs.get_devices()
                gpus = [d for d in prefs.devices if d.type != "CPU"]
                if gpus:
                    for d in prefs.devices:
                        d.use = d.type != "CPU"
                    scene.cycles.device = "GPU"
                    return dev_type
            except Exception:
                continue
    except Exception:
        pass
    return "CPU"


def setup_render():
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.samples = RENDER_SAMPLES
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.01
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.max_bounces = 12
    cy.glossy_bounces = 6
    cy.sample_clamp_indirect = 10.0
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"
    # "Standard" menjaga merah tetap pekat (AgX/Filmic membuat merah terang jadi pucat/pink)
    scene.view_settings.view_transform = "Standard"
    for look in ("Medium High Contrast", "AgX - Medium High Contrast", "None"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue
    scene.view_settings.exposure = EXPOSURE
    scene.view_settings.gamma = 1.0
    scene.render.filter_size = 0.9          # lebih tajam

    # Compositor: penajaman halus
    try:
        scene.use_nodes = True
        nt = scene.node_tree
        rl = next((n for n in nt.nodes if n.type == "R_LAYERS"), None) or nt.nodes.new("CompositorNodeRLayers")
        comp = next((n for n in nt.nodes if n.type == "COMPOSITE"), None) or nt.nodes.new("CompositorNodeComposite")
        sharp = nt.nodes.new("CompositorNodeFilter")
        sharp.filter_type = "SHARPEN"
        sharp.inputs["Fac"].default_value = 0.25
        nt.links.new(rl.outputs["Image"], sharp.inputs["Image"])
        nt.links.new(sharp.outputs["Image"], comp.inputs["Image"])
    except Exception as e:
        print("Compositor dilewati:", e)
    print("Render device:", enable_gpu())


# =============================================================
# 7. EKSEKUSI — VERSI WEB (hanya produk, export GLB)
# =============================================================
# Geometri penuh dari script asli.
# Tanpa backdrop, lampu, kamera, render.

EXPORT_GLB = r"C:\users\lenovo\Downloads\REAM.glb"

print(f"Ream WEB: lebar={W*1000:.0f} mm, tebal={T*1000:.1f} mm, tinggi={H*1000:.0f} mm")
img = load_image()
wrapper_mat = make_wrapper_material(img)
build_paper_block()
build_wrapper(wrapper_mat)

# Sembunyikan object non-produk (jika ada dari session sebelumnya)
skip_keys = ("Backdrop", "Camera", "Key_", "Fill_", "Top_Soft", "Rim_", "Focus", "Sun", "Area", "Light")
for ob in list(bpy.data.objects):
    if ob.type in ("LIGHT", "CAMERA"):
        ob.hide_set(True)
        ob.hide_render = True
        continue
    if any(k in ob.name for k in skip_keys):
        ob.hide_set(True)
        ob.hide_render = True

# Pastikan mesh produk terlihat
for ob in bpy.data.objects:
    if ob.type == "MESH" and not any(k in ob.name for k in skip_keys):
        ob.hide_set(False)
        ob.hide_render = False

bpy.ops.export_scene.gltf(
    filepath=EXPORT_GLB,
    export_format="GLB",
    use_selection=False,
    use_visible=True,
    export_apply=True,
    export_texcoords=True,
    export_normals=True,
    export_materials="EXPORT",
    export_cameras=False,
    export_lights=False,
)
print("Export selesai:", EXPORT_GLB)
print("Object diexport:", [o.name for o in bpy.data.objects if o.type == "MESH" and not o.hide_render])