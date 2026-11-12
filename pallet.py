# =============================================================
# BLENDER SCRIPT A1ONE PALLET — VERSI WEB
# Hanya produk (pallet + box + aksesoris).
# Tanpa lantai, lampu, kamera.
# Export otomatis ke GLB.
# =============================================================

import bpy
import bmesh
import math
import os

# ================= KONFIGURASI =================

TOP_IMAGE = r"C:/users/lenovo/downloads/top_box.png"
BOTTOM_IMAGE = r"C:/users/lenovo/downloads/bottom_box.png"
EXPORT_GLB = r"C:/users/lenovo/downloads/pallet.glb"

BOX_W = 0.220
BOX_L = 0.305
BOX_H = 0.216
SHORT_H = 0.108
LID_DEPTH = 0.065
THICK = 0.003
GAP = 0.001
END_FLAPS = True
FLAP_GAP = 0.001
SHOW_PAPER = True

INNER_COLOR = (0.62, 0.43, 0.26, 1.0)
LID_FALLBACK = (0.75, 0.10, 0.10, 1.0)
BODY_FALLBACK = (0.95, 0.95, 0.95, 1.0)

BOTTOM_SIZE = (553, 680)
BOTTOM_PANEL_PX = (115, 436, 227, 453)
BOTTOM_OUTER_PX = (0, 549, 0, 676)

TOP_SIZE = (535, 685)
TOP_PANEL_PX = (100, 434, 105, 580)
TOP_OUTER_PX = (1, 533, 6, 678)

N_LAYERS = 4
LAYOUT_GAP = 0.002
LAYER_CLEAR = 0.0006

PAL_A = 1.00
PAL_B = 1.20
PAL_H = 0.145

SHOW_CORNERS = True
SHOW_LONG_EDGE_L = True
SHOW_TOPSHEET = True
SHOW_STRAP_PROT = True
SHOW_STRAPS = True
SHOW_WRAP = False      # matikan untuk web (transparansi sering bermasalah)
SHOW_LABEL = False     # matikan untuk web

CORNER_SIDE_X = -1
CORNER_FLANGE = 0.09
CORNER_T = 0.004

LONG_EDGE_T = 0.004
LONG_EDGE_LEG = 0.055

SHEET_T = 0.004
SHEET_M = 0.002

STRAPS_Y = (-0.32, 0.0, 0.32)

STRAP_PROT_LEN = 0.14
STRAP_PROT_LEG = 0.05
STRAP_PROT_T = 0.004

STRAP_W = 0.015
STRAP_T = 0.0022
WRAP_MARGIN = 0.006

# ================= UKURAN TURUNAN =================

BX_S = BOX_W + 2 * (THICK + GAP)
BX_L = BOX_L + 2 * (THICK + GAP)

PITCH = BOX_H + THICK + LAYER_CLEAR

SPAN_X = 3 * BX_L + 2 * LAYOUT_GAP
SPAN_Y = 2 * BX_L + 2 * BX_S + 3 * LAYOUT_GAP

STACK_H = N_LAYERS * PITCH

ROOT = None
MASTER = None
OBJ_COLL = None


# =============================================================
# UTILITAS
# =============================================================

def clear_old():
    for ob in list(bpy.data.objects):
        if ob.name.startswith("Pal_"):
            bpy.data.objects.remove(ob, do_unlink=True)
    old = bpy.data.collections.get("Pal_BoxMaster")
    if old:
        bpy.data.collections.remove(old)


def uv_from_px(panel_px, outer_px, size):
    W, H = size
    x0, x1, y0, y1 = panel_px
    panel = (x0 / W, x1 / W, 1 - y1 / H, 1 - y0 / H)
    a0, a1, b0, b1 = outer_px
    outer = (a0 / W, a1 / W, 1 - b1 / H, 1 - b0 / H)
    return panel, outer


# =============================================================
# MATERIAL
# =============================================================

def make_material(name, img_path, fallback=(0.8, 0.8, 0.8, 1)):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    bsdf.inputs["Roughness"].default_value = 0.55
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if img_path and os.path.exists(img_path):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-300, 0)
        tex.image = bpy.data.images.load(img_path, check_existing=True)
        tex.extension = 'EXTEND'
        tex.interpolation = 'Cubic'
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        if img_path:
            print("[WARNING] Gambar tidak ditemukan:", img_path)
        bsdf.inputs["Base Color"].default_value = fallback
    return mat


def make_proc_mat(name, c1, c2, scale=8.0, stretch=(1, 1, 1), rough=0.8, bump=0.15, detail=6.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Base Color"].default_value = c1
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    try:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.location = (-600, 0)
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.location = (-400, 0)
        mp.inputs["Scale"].default_value = stretch
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.location = (-200, 0)
        nz.inputs["Scale"].default_value = scale
        nz.inputs["Detail"].default_value = detail
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.location = (100, 100)
        ramp.color_ramp.elements[0].color = c1
        ramp.color_ramp.elements[1].color = c2
        bp = nt.nodes.new("ShaderNodeBump")
        bp.location = (100, -150)
        bp.inputs["Strength"].default_value = bump
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
        nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], bsdf.inputs["Normal"])
    except Exception as e:
        print("[INFO] Node prosedural dilewati:", e)
    return mat


def make_plain_mat(name, color, rough=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# =============================================================
# GEOMETRI
# =============================================================

def cube(name, center, size, mat, bevel=0.0, parent=True):
    me = bpy.data.meshes.new(name + "_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.location = center
    ob.scale = size
    me.materials.append(mat)
    if parent:
        ob.parent = ROOT
    if bevel > 0:
        b = ob.modifiers.new("Bevel", 'BEVEL')
        b.width = bevel
        b.segments = 1
        b.limit_method = 'ANGLE'
    return ob


def make_part(name, W, L, depth_fb, depth_lr, panel, outer,
              mat_print, mat_inner, bevel=0.0008, end_flaps=False, flap_gap=0.0):
    w = W / 2
    l = L / 2
    zt = 0.0
    zfb = -depth_fb
    zlr = -depth_lr
    u0, u1, v0, v1 = panel
    oL, oR, oB, oT = outer
    mu = lambda x: u0 + (x + w) / W * (u1 - u0)
    mv = lambda y: v0 + (y + l) / L * (v1 - v0)

    faces = [
        [((-w, -l, zt), (mu(-w), mv(-l))), ((w, -l, zt), (mu(w), mv(-l))),
         ((w, l, zt), (mu(w), mv(l))), ((-w, l, zt), (mu(-w), mv(l)))],
        [((-w, -l, zfb), (mu(-w), oB)), ((w, -l, zfb), (mu(w), oB)),
         ((w, -l, zt), (mu(w), v0)), ((-w, -l, zt), (mu(-w), v0))],
        [((w, l, zfb), (mu(w), oT)), ((-w, l, zfb), (mu(-w), oT)),
         ((-w, l, zt), (mu(-w), v1)), ((w, l, zt), (mu(w), v1))],
    ]
    faces.append([((-w, l, zlr), (oL, mv(l))), ((-w, -l, zlr), (oL, mv(-l))),
                  ((-w, -l, zt), (u0, mv(-l))), ((-w, l, zt), (u0, mv(l)))])
    faces.append([((w, -l, zlr), (oR, mv(-l))), ((w, l, zlr), (oR, mv(l))),
                  ((w, l, zt), (u1, mv(l))), ((w, -l, zt), (u1, mv(-l)))])

    if end_flaps:
        g = flap_gap / 2.0
        wf = w - THICK
        for (ya, yb, v_fold, v_free, fold_at_ya) in (
                (-l + THICK, -g, v0, oB, True),
                (g, l - THICK, v1, oT, False)):
            span = yb - ya
            def t(y):
                return (y - ya) / span if fold_at_ya else (yb - y) / span
            uL = lambda y: u0 + t(y) * (oL - u0)
            uR = lambda y: u1 + t(y) * (oR - u1)
            faces.append([((-wf, yb, zfb), (uL(yb), v_free)), ((-wf, ya, zfb), (uL(ya), v_free)),
                          ((-wf, ya, zt), (uL(ya), v_fold)), ((-wf, yb, zt), (uL(yb), v_fold))])
            faces.append([((wf, ya, zfb), (uR(ya), v_free)), ((wf, yb, zfb), (uR(yb), v_free)),
                          ((wf, yb, zt), (uR(yb), v_fold)), ((wf, ya, zt), (uR(ya), v_fold))])

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    vcache = {}
    def get_v(co):
        key = tuple(round(c, 6) for c in co)
        if key not in vcache:
            vcache[key] = bm.verts.new(co)
        return vcache[key]
    for f in faces:
        face = bm.faces.new([get_v(co) for co, _ in f])
        for loop, (_, uv) in zip(face.loops, f):
            loop[uv_layer].uv = uv

    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    OBJ_COLL.objects.link(ob)
    ob.data.materials.append(mat_print)
    ob.data.materials.append(mat_inner)
    sol = ob.modifiers.new("Thickness", 'SOLIDIFY')
    sol.thickness = THICK
    sol.offset = -1.0
    sol.material_offset = 1
    sol.material_offset_rim = 1
    bev = ob.modifiers.new("Bevel", 'BEVEL')
    bev.width = bevel
    bev.segments = 2
    bev.limit_method = 'ANGLE'
    return ob


def make_paper_stack(mat):
    sx = BOX_W - 2 * THICK - 0.0004
    sy = BOX_L - (4 if END_FLAPS else 2) * THICK - 0.0004
    sz = BOX_H - THICK
    me = bpy.data.meshes.new("Pal_BoxM_Paper_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Pal_BoxM_Paper", me)
    OBJ_COLL.objects.link(ob)
    ob.scale = (sx, sy, sz)
    ob.location = (0, 0, THICK + sz / 2)
    ob.data.materials.append(mat)
    return ob


def build_box_master():
    global MASTER, OBJ_COLL
    MASTER = bpy.data.collections.new("Pal_BoxMaster")
    OBJ_COLL = MASTER
    top_panel, top_outer = uv_from_px(TOP_PANEL_PX, TOP_OUTER_PX, TOP_SIZE)
    bot_panel, bot_outer = uv_from_px(BOTTOM_PANEL_PX, BOTTOM_OUTER_PX, BOTTOM_SIZE)
    mat_top = make_material("Pal_BoxTopPrint", TOP_IMAGE, LID_FALLBACK)
    mat_bottom = make_material("Pal_BoxBottomPrint", BOTTOM_IMAGE, BODY_FALLBACK)
    mat_inner = make_material("Pal_BoxInner", None, INNER_COLOR)
    mat_paper = make_material("Pal_BoxPaper", None, (0.93, 0.93, 0.91, 1))
    bottom = make_part("Pal_BoxM_Bottom", BOX_L, BOX_W,
                       depth_fb=BOX_H, depth_lr=SHORT_H,
                       panel=bot_panel, outer=bot_outer,
                       mat_print=mat_bottom, mat_inner=mat_inner,
                       end_flaps=END_FLAPS, flap_gap=FLAP_GAP)
    bottom.rotation_euler = (math.pi, 0, math.pi / 2)
    if SHOW_PAPER:
        make_paper_stack(mat_paper)
    off = 2 * (THICK + GAP)
    top = make_part("Pal_BoxM_Top", BOX_W + off, BOX_L + off,
                    depth_fb=LID_DEPTH, depth_lr=LID_DEPTH,
                    panel=top_panel, outer=top_outer,
                    mat_print=mat_top, mat_inner=mat_inner, bevel=0.0012)
    top.location = (0, 0, BOX_H + THICK)


def place_box(name, x, y, z, rot):
    e = bpy.data.objects.new(name, None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = MASTER
    e.empty_display_size = 0.05
    e.location = (x, y, z)
    e.rotation_euler = (0, 0, rot)
    bpy.context.collection.objects.link(e)
    e.parent = ROOT


LAYER_ROWS = {
    1: [('P', 4), ('L', 3), ('L', 3), ('P', 4)],
    2: [('L', 3), ('P', 4), ('P', 4), ('L', 3)],
}


def layer_positions(kind):
    res = []
    y = SPAN_Y / 2
    for orientation, n in LAYER_ROWS[kind]:
        hy = BX_L if orientation == 'P' else BX_S
        wx = BX_S if orientation == 'P' else BX_L
        yc = y - hy / 2
        step = (SPAN_X - wx) / (n - 1) if n > 1 else 0
        for i in range(n):
            xc = -SPAN_X / 2 + wx / 2 + i * step
            rot = 0.0 if orientation == 'P' else math.pi / 2
            res.append((xc, yc, rot))
        y -= hy + LAYOUT_GAP
    return res


def build_stack():
    count = 0
    for k in range(N_LAYERS):
        kind = 1 if k % 2 == 0 else 2
        zb = PAL_H + k * PITCH
        for idx, (x, y, rot) in enumerate(layer_positions(kind)):
            place_box(f"Pal_Box_L{k+1}_{idx:02d}", x, y, zb, rot)
            count += 1
    return count


def build_pallet(mat):
    A, B = PAL_A, PAL_B
    t_bot = 0.022
    t_deck = 0.022
    t_str = 0.022
    z_bot0 = 0.0
    z_blk0 = t_bot
    z_str0 = PAL_H - t_deck - t_str
    z_deck0 = PAL_H - t_deck
    blk_h = z_str0 - z_blk0
    bv = 0.002
    xs = (-A / 2 + 0.05, 0.0, A / 2 - 0.05)
    ys = (-B / 2 + 0.06, 0.0, B / 2 - 0.06)
    n_top = 7
    bw = 0.115
    step = (B - bw) / (n_top - 1)
    for i in range(n_top):
        y = -B / 2 + bw / 2 + i * step
        cube(f"Pal_Deck{i}", (0, y, z_deck0 + t_deck / 2), (A, bw, t_deck), mat, bv)
    for k, x in enumerate(xs):
        cube(f"Pal_Stringer{k}", (x, 0, z_str0 + t_str / 2), (0.095, B, t_str), mat, bv)
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            cube(f"Pal_Block{i}{j}", (x, y, z_blk0 + blk_h / 2), (0.095, 0.10, blk_h), mat, bv)
    for j, y in enumerate(ys):
        cube(f"Pal_Base{j}", (0, y, z_bot0 + t_bot / 2), (A, 0.10, t_bot), mat, bv)


def top_sheet_z():
    return PAL_H + STACK_H + (SHEET_T if SHOW_TOPSHEET else 0.0)


def top_long_edge_z():
    return top_sheet_z() + (LONG_EDGE_T if SHOW_LONG_EDGE_L else 0.0)


def build_long_edge_L(mat):
    if not SHOW_LONG_EDGE_L:
        return
    X, Y = SPAN_X, SPAN_Y
    t, leg = LONG_EDGE_T, LONG_EDGE_LEG
    edge_x = X / 2 + SHEET_M
    z_base = top_sheet_z()
    for sx in (-1, 1):
        name = f"Pal_LongEdgeL_{sx}"
        cube(name + "_Top", (sx * (edge_x - leg / 2), 0, z_base + t / 2),
             (leg, Y + 2 * SHEET_M, t), mat, 0.0008)
        cube(name + "_Side", (sx * (edge_x + t / 2), 0, z_base - leg / 2 + t / 2),
             (t, Y + 2 * SHEET_M, leg + t), mat, 0.0008)


def build_corner_protectors(mat):
    X, Y = SPAN_X, SPAN_Y
    t, fl = CORNER_T, CORNER_FLANGE
    H = STACK_H
    zc = PAL_H + H / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            n = f"Pal_Corner_V_{sx}_{sy}"
            cube(n + "_A", (sx * (X / 2 - fl / 2 + t / 2), sy * (Y / 2 + t / 2), zc),
                 (fl + t, t, H), mat, 0.0008)
            cube(n + "_B", (sx * (X / 2 + t / 2), sy * (Y / 2 - fl / 2), zc),
                 (t, fl, H), mat, 0.0008)
    z_base = top_long_edge_z()
    for sy in (-1, 1):
        n = f"Pal_Corner_H_{sy}"
        cube(n, (0, sy * (Y / 2 - fl / 2), z_base + t / 2),
             (X + 2 * SHEET_M, fl, t), mat, 0.0008)


def build_topsheet(mat):
    cube("Pal_TopSheet", (0, 0, PAL_H + STACK_H + SHEET_T / 2),
         (SPAN_X + 2 * SHEET_M, SPAN_Y + 2 * SHEET_M, SHEET_T), mat, 0.0008)


def top_corner_z():
    return top_long_edge_z() + CORNER_T


def top_strap_protector_z():
    return top_corner_z() + STRAP_PROT_T


def build_strap_protectors(mat):
    Xe = SPAN_X / 2 + SHEET_M
    zs = top_corner_z()
    tp, leg, ln = STRAP_PROT_T, STRAP_PROT_LEG, STRAP_PROT_LEN
    for sx in (-1, 1):
        for k, ys in enumerate(STRAPS_Y):
            n = f"Pal_StrapProt_{sx}_{k}"
            cube(n + "_V", (sx * (Xe + tp / 2), ys, zs - leg / 2 + tp / 2),
                 (tp, ln, leg + tp), mat, 0.0008)
            cube(n + "_H", (sx * (Xe + tp - leg / 2), ys, zs + tp / 2),
                 (leg, ln, tp), mat, 0.0008)


def build_straps(mat, mat_clip):
    Xe = SPAN_X / 2 + SHEET_M
    zs = top_strap_protector_z() if SHOW_STRAP_PROT else top_corner_z()
    st, sw = STRAP_T, STRAP_W
    z_top = zs + st / 2
    h = (zs + st) - PAL_H
    xo = Xe + (STRAP_PROT_T if SHOW_STRAP_PROT else 0.0) + st / 2
    for k, ys in enumerate(STRAPS_Y):
        cube(f"Pal_Strap{k}_Top", (0, ys, z_top),
             (2 * (Xe + (STRAP_PROT_T if SHOW_STRAP_PROT else 0.0) + st), sw, st), mat)
        for sx in (-1, 1):
            cube(f"Pal_Strap{k}_Side{sx}", (sx * xo, ys, PAL_H + h / 2),
                 (st, sw, h), mat)
        cube(f"Pal_Strap{k}_Clip", (0.0, ys, z_top + st / 2 + 0.0012),
             (0.032, sw + 0.006, 0.0024), mat_clip, 0.0004)


def export_glb(filepath):
    """
    Export produk saja. Object di collection master (Pal_BoxMaster)
    sering tidak ada di View Layer, jadi tidak bisa di-select.
    Solusi: link collection ke scene, lalu export semua yang terlihat
    tanpa bergantung pada selection.
    """
    # Pastikan collection master terhubung ke scene agar instance terbaca
    #if MASTER is not None:
        #scn_coll = bpy.context.scene.collection
        #if MASTER.name not in scn_coll.children:
            #try:
                #scn_coll.children.link(MASTER)
            #except RuntimeError:
                #pass  # sudah terhubung

    # Sembunyikan object non-produk (jika ada)
    skip_keys = ("Floor", "Sun", "Fill", "Cam", "Target", "World", "Backdrop")
    for ob in bpy.data.objects:
        if any(k in ob.name for k in skip_keys):
            ob.hide_set(True)
            ob.hide_render = True
        else:
            ob.hide_set(False)
            ob.hide_render = False

    # Pastikan semua image texture tertanam di file GLB.
    for img in bpy.data.images:
        try:
            if img.source == 'FILE' and img.has_data:
                img.pack()
        except Exception as e:
            print("[WARNING] Gagal pack image", img.name, ":", e)

    # Export semua object yang visible (tanpa use_selection)
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        use_selection=False,
        use_visible=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
        export_cameras=False,
        export_lights=False,
        export_extras=False,
    )
    print(f"GLB diexport ke: {filepath}")


# =============================================================
# MAIN
# =============================================================

def main():
    global ROOT, OBJ_COLL
    clear_old()
    ROOT = bpy.data.objects.new("Pal_Root", None)
    bpy.context.collection.objects.link(ROOT)

    # MATERIAL GLB-SAFE:
    # GLB/glTF tidak membawa node procedural Noise/ColorRamp/Bump secara langsung.
    # Karena itu gunakan Principled BSDF sederhana agar corner protector,
    # top sheet, edge protector, dan kayu tidak berubah putih setelah export.
    m_wood = make_plain_mat(
        "Pal_Wood",
        (0.62, 0.45, 0.27, 1.0),
        rough=0.82,
        metallic=0.0
    )
    m_kraft = make_plain_mat(
        "Pal_Kraft",
        (0.61, 0.49, 0.34, 1.0),
        rough=0.90,
        metallic=0.0
    )
    m_strap = make_plain_mat("Pal_StrapMat", (0.05, 0.55, 0.22, 1), 0.35)
    m_clip = make_plain_mat("Pal_ClipMat", (0.65, 0.66, 0.68, 1), 0.3, 1.0)

    build_box_master()
    OBJ_COLL = bpy.context.collection
    n = build_stack()
    build_pallet(m_wood)

    if SHOW_TOPSHEET:
        build_topsheet(m_kraft)
    if SHOW_LONG_EDGE_L:
        build_long_edge_L(m_kraft)
    if SHOW_CORNERS:
        build_corner_protectors(m_kraft)
    if SHOW_STRAP_PROT:
        build_strap_protectors(m_kraft)
    if SHOW_STRAPS:
        build_straps(m_strap, m_clip)

    # TIDAK memanggil add_scene_extras (lantai, lampu, kamera)

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'MATERIAL'

    print(f"Pallet WEB selesai: {n} box, {N_LAYERS} layer (tanpa lantai/lampu/kamera)")
    export_glb(EXPORT_GLB)


main()
