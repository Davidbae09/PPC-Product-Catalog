# =============================================================
#  BLENDER SCRIPT : Box Kertas A4  (tutup merah + wadah putih)
#  Lipatan wadah mengikuti sketsa & foto:
#   - Dinding PANJANG  : tinggi penuh. Ujungnya dilipat ke dalam
#                        -> 2 flap tinggi penuh di tiap sisi pendek.
#   - Panel PENDEK     : setengah tinggi, dilipat menutupi bagian
#                        bawah flap (bagian atas = 2 flap + seam).
#   - Tutup            : 4 dinding sama tinggi (tidak berubah).
#  Blender 3.x / 4.x  ->  Scripting > New > Paste > Run Script
# =============================================================
import bpy, bmesh, math, os

# ---------------- KONFIGURASI ----------------
TOP_IMAGE    = r"C:/users/lenovo/downloads/top_box.png"      # Top_Box.png
BOTTOM_IMAGE = r"C:/users/lenovo/downloads/bottom_box.png"   # Bottom_Box.png

BOX_W      = 0.220   # lebar  (sumbu X) -> sisi pendek
BOX_L      = 0.305   # panjang (sumbu Y) -> sisi panjang
BOX_H      = 0.216   # tinggi dinding PANJANG wadah
SHORT_H    = 0.108   # tinggi flap dinding PENDEK (~50%)
LID_DEPTH  = 0.065   # tinggi dinding tutup
THICK      = 0.003   # tebal karton
GAP        = 0.001   # celah tutup & wadah
LID_LIFT   = 0.0     # isi mis. 0.15 untuk mengangkat tutup (preview)

# ---- Lipatan sisi pendek (sesuai sketsa & foto) ----
# 1) Ujung tiap dinding PANJANG dilipat ke dalam -> 2 flap tinggi penuh,
#    masing-masing setengah lebar sisi pendek, bertemu di tengah (garis seam).
# 2) Panel sisi pendek (setengah tinggi) dilipat menutupi bagian bawah flap.
END_FLAPS = True
FLAP_GAP  = 0.001   # celah seam di tengah antar flap

SHOW_PAPER = True    # tumpukan kertas putih yang tampak di celah

INNER_COLOR = (0.62, 0.43, 0.26, 1.0)   # cokelat karton (tepi & bagian dalam)

# ---- Koordinat piksel pada gambar dieline (diukur dari file) ----
BOTTOM_SIZE  = (553, 680)
BOTTOM_PANEL_PX = (115, 436, 227, 453)   # x_kiri, x_kanan, y_atas, y_bawah
BOTTOM_OUTER_PX = (0, 549, 0, 676)

TOP_SIZE     = (535, 685)
TOP_PANEL_PX = (100, 434, 105, 580)
TOP_OUTER_PX = (1, 533, 6, 678)
# ---------------------------------------------


def uv_from_px(panel_px, outer_px, size):
    """piksel (y dari atas) -> UV (v dari bawah). Return (panel, outer)."""
    W, H = size
    x0, x1, y0, y1 = panel_px
    panel = (x0 / W, x1 / W, 1 - y1 / H, 1 - y0 / H)          # u0,u1,v0,v1
    a0, a1, b0, b1 = outer_px
    outer = (a0 / W, a1 / W, 1 - b1 / H, 1 - b0 / H)          # oL,oR,oB,oT
    return panel, outer


def clear_old():
    for ob in list(bpy.data.objects):
        if ob.name.startswith(("Box_", "BoxCam", "BoxSun")):
            bpy.data.objects.remove(ob, do_unlink=True)


def make_material(name, img_path, fallback=(0.8, 0.8, 0.8, 1)):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out  = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (100, 0)
    bsdf.inputs["Roughness"].default_value = 0.55
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if img_path and os.path.exists(img_path):
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-300, 0)
        tex.image = bpy.data.images.load(img_path, check_existing=True)
        tex.extension = 'EXTEND'
        tex.interpolation = 'Cubic'
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        if img_path:
            print(f"[WARNING] Gambar tidak ditemukan: {img_path}")
        bsdf.inputs["Base Color"].default_value = fallback
    return mat


def make_part(name, W, L, depth_fb, depth_lr, panel, outer,
              mat_print, mat_inner, bevel=0.0008,
              end_flaps=False, flap_gap=0.0):
    """
    Bagian terbuka: muka di z=0, dinding turun ke bawah.
      depth_fb : tinggi dinding depan/belakang (y = -l / +l)
      depth_lr : tinggi dinding kiri/kanan     (x = -w / +w)
      end_flaps: True -> ujung dinding depan/belakang dilipat ke dalam
                 menjadi flap tinggi penuh di sisi kiri/kanan (tepat di
                 belakang panel kiri/kanan), bertemu di tengah.
    UV mengikuti dieline silang (panel tengah + 4 sayap + 4 sudut).
    """
    w, l = W / 2, L / 2
    zt = 0.0
    zfb, zlr = -depth_fb, -depth_lr
    u0, u1, v0, v1 = panel
    oL, oR, oB, oT = outer
    mu = lambda x: u0 + (x + w) / W * (u1 - u0)
    mv = lambda y: v0 + (y + l) / L * (v1 - v0)

    faces = [
        # muka (normal +Z)
        [((-w, -l, zt), (mu(-w), mv(-l))), (( w, -l, zt), (mu(w), mv(-l))),
         (( w,  l, zt), (mu(w),  mv(l))),  ((-w,  l, zt), (mu(-w), mv(l)))],
        # depan (y=-l) -> sayap bawah gambar
        [((-w, -l, zfb), (mu(-w), oB)), (( w, -l, zfb), (mu(w), oB)),
         (( w, -l, zt),  (mu(w),  v0)), ((-w, -l, zt),  (mu(-w), v0))],
        # belakang (y=+l) -> sayap atas gambar
        [(( w,  l, zfb), (mu(w),  oT)), ((-w,  l, zfb), (mu(-w), oT)),
         ((-w,  l, zt),  (mu(-w), v1)), (( w,  l, zt),  (mu(w),  v1))],
    ]

    # kiri (x=-w) -> sayap kiri gambar  (panel sisi pendek, setengah tinggi)
    faces.append([((-w,  l, zlr), (oL, mv(l))),  ((-w, -l, zlr), (oL, mv(-l))),
                  ((-w, -l, zt),  (u0, mv(-l))), ((-w,  l, zt),  (u0, mv(l)))])
    # kanan (x=+w) -> sayap kanan gambar
    faces.append([(( w, -l, zlr), (oR, mv(-l))), (( w,  l, zlr), (oR, mv(l))),
                  (( w,  l, zt),  (u1, mv(l))),  (( w, -l, zt),  (u1, mv(-l)))])

    # ---- flap ujung (dilipat ke dalam, di belakang panel pendek) ----
    if end_flaps:
        g  = flap_gap / 2.0
        wf = w - THICK                 # tepat di belakang panel pendek
        # flap dari dinding DEPAN (y=-l): dari y=-l+THICK sampai y=-g
        # flap dari dinding BELAKANG (y=+l): dari y=+g sampai y=+l-THICK
        for (ya, yb, v_fold, v_free, fold_at_ya) in (
                (-l + THICK, -g, v0, oB, True),
                ( g, l - THICK, v1, oT, False)):
            span = yb - ya
            def t(y):   # 0 di lipatan dinding, 1 di tepi tengah
                return (y - ya) / span if fold_at_ya else (yb - y) / span
            uL = lambda y: u0 + t(y) * (oL - u0)
            uR = lambda y: u1 + t(y) * (oR - u1)
            # kiri (normal -X)
            faces.append([((-wf, yb, zfb), (uL(yb), v_free)), ((-wf, ya, zfb), (uL(ya), v_free)),
                          ((-wf, ya, zt),  (uL(ya), v_fold)), ((-wf, yb, zt),  (uL(yb), v_fold))])
            # kanan (normal +X)
            faces.append([(( wf, ya, zfb), (uR(ya), v_free)), (( wf, yb, zfb), (uR(yb), v_free)),
                          (( wf, yb, zt),  (uR(yb), v_fold)), (( wf, ya, zt),  (uR(ya), v_fold))])

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
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat_print)   # slot 0 : sisi cetak (luar)
    ob.data.materials.append(mat_inner)   # slot 1 : dalam + tepi

    sol = ob.modifiers.new("Thickness", 'SOLIDIFY')
    sol.thickness = THICK
    sol.offset = -1.0                     # tebal ke arah dalam
    sol.material_offset = 1
    sol.material_offset_rim = 1

    bev = ob.modifiers.new("Bevel", 'BEVEL')
    bev.width = bevel
    bev.segments = 2
    bev.limit_method = 'ANGLE'
    return ob


def make_paper_stack(mat):
    """Tumpukan kertas di dalam wadah (terlihat lewat celah dinding pendek)."""
    sx = BOX_W - 2 * THICK - 0.0004
    # sisi pendek (sumbu Y): sisakan ruang untuk panel + flap
    sy = BOX_L - (4 if END_FLAPS else 2) * THICK - 0.0004
    sz = BOX_H - THICK
    me = bpy.data.meshes.new("Box_Paper_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Box_Paper", me)
    bpy.context.collection.objects.link(ob)
    ob.scale = (sx, sy, sz)
    ob.location = (0, 0, THICK + sz / 2)
    ob.data.materials.append(mat)
    return ob


def add_camera_light():
    bpy.ops.object.light_add(type='SUN', location=(1, -1, 2))
    sun = bpy.context.object; sun.name = "BoxSun"
    sun.data.energy = 3
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))

    bpy.ops.object.camera_add(location=(0.80, -0.85, 0.55))
    cam = bpy.context.object; cam.name = "BoxCam"
    cam.data.lens = 55
    tgt = bpy.data.objects.new("Box_Target", None)
    tgt.location = (0, 0, BOX_H * 0.5)
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    bpy.context.scene.camera = cam


def main():
    clear_old()
    top_panel, top_outer = uv_from_px(TOP_PANEL_PX, TOP_OUTER_PX, TOP_SIZE)
    bot_panel, bot_outer = uv_from_px(BOTTOM_PANEL_PX, BOTTOM_OUTER_PX, BOTTOM_SIZE)

    mat_top    = make_material("Box_TopPrint",    TOP_IMAGE,    (0.75, 0.1, 0.1, 1))
    mat_bottom = make_material("Box_BottomPrint", BOTTOM_IMAGE, (0.95, 0.95, 0.95, 1))
    mat_inner  = make_material("Box_Inner", None, INNER_COLOR)
    mat_paper  = make_material("Box_PaperMat", None, (0.93, 0.93, 0.91, 1))

    # ---------- BOTTOM (wadah) ----------
    # Lokal: panjang di X. Dinding kiri/kanan = sisi PENDEK (2 flap rendah),
    # dinding depan/belakang = sisi PANJANG (penuh).
    # Dibalik (rot X 180) agar jadi wadah, lalu diputar Z 90 (panjang -> sumbu Y).
    bottom = make_part("Box_Bottom", BOX_L, BOX_W,
                       depth_fb=BOX_H, depth_lr=SHORT_H,
                       panel=bot_panel, outer=bot_outer,
                       mat_print=mat_bottom, mat_inner=mat_inner,
                       end_flaps=END_FLAPS, flap_gap=FLAP_GAP)
    bottom.rotation_euler = (math.pi, 0, math.pi / 2)
    bottom.location = (0, 0, 0)

    if SHOW_PAPER:
        make_paper_stack(mat_paper)

    # ---------- TOP (tutup) ----------
    off = 2 * (THICK + GAP)
    top = make_part("Box_Top", BOX_W + off, BOX_L + off,
                    depth_fb=LID_DEPTH, depth_lr=LID_DEPTH,
                    panel=top_panel, outer=top_outer,
                    mat_print=mat_top, mat_inner=mat_inner, bevel=0.0012)
    top.location = (0, 0, BOX_H + THICK + LID_LIFT)

    # TIDAK membuat kamera & lampu (versi web)

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'MATERIAL'

    # Sembunyikan object non-produk jika ada
    skip = ("Cam", "Sun", "Target", "Light", "Floor", "Wrap", "Stretch")
    for ob in bpy.data.objects:
        if any(k in ob.name for k in skip):
            ob.hide_set(True)
            ob.hide_render = True

    export_path = r"C:/users/lenovo/downloads/carton.glb"
    bpy.ops.export_scene.gltf(
        filepath=export_path,
        export_format='GLB',
        use_selection=False,
        use_visible=True,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
    )
    print("Box web selesai. GLB:", export_path)


main()