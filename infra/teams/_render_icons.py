"""Generate Teams app icons (color.png 192x192, outline.png 32x32)."""
from PIL import Image, ImageDraw


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def render_color(out_path: str) -> None:
    W = 192
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

    g1 = (79, 70, 229)   # indigo
    g2 = (124, 58, 237)  # violet
    grad = Image.new("RGBA", (W, W))
    gp = grad.load()
    for y in range(W):
        for x in range(W):
            t = (x + y) / (W * 2)
            r, g, b = lerp(g1, g2, t)
            gp[x, y] = (r, g, b, 255)

    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W, W), radius=40, fill=255)
    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)
    draw.ellipse((22, 22, W - 22, W - 22), outline=(255, 255, 255, 46), width=2)
    draw.ellipse((38, 38, W - 38, W - 38), outline=(255, 255, 255, 72), width=2)

    bolt = [(102, 38), (70, 102), (92, 102), (84, 154), (124, 86), (100, 86)]
    draw.polygon(bolt, fill=(252, 211, 77), outline=(255, 251, 235))
    for i in range(len(bolt)):
        x1, y1 = bolt[i]
        x2, y2 = bolt[(i + 1) % len(bolt)]
        draw.line((x1, y1, x2, y2), fill=(255, 251, 235), width=3)

    draw.ellipse((137, 137, 159, 159), fill=(16, 185, 129),
                 outline=(255, 255, 255), width=3)
    draw.ellipse((144, 144, 152, 152), fill=(255, 255, 255))
    img.save(out_path, "PNG")


def render_outline(out_path: str) -> None:
    o = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    od = ImageDraw.Draw(o)
    poly = [(17, 5), (11, 17), (15, 17), (13, 27), (22, 14), (17, 14), (19, 5)]
    od.polygon(poly, fill=(255, 255, 255, 255))
    od.line(poly + [poly[0]], fill=(255, 255, 255, 255), width=1)
    o.save(out_path, "PNG")


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    render_color(f"{out_dir}/color.png")
    render_outline(f"{out_dir}/outline.png")
    print(f"wrote {out_dir}/color.png + outline.png")
