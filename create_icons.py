#!/usr/bin/env python3
"""
创建YouTube下载工具图标
设计理念：结合YouTube红色主题 + 下载箭头 + 现代化设计
"""

import os
from pathlib import Path
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("需要安装PIL库：pip install Pillow")

def create_youtube_downloader_icon(size, output_path):
    """创建YouTube下载工具图标"""
    if not PIL_AVAILABLE:
        return False
        
    # 创建透明背景的图像
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 对于小尺寸图标，使用简化设计
    is_small = size <= 32
    
    # 颜色定义
    youtube_red = (255, 0, 0)      # YouTube红色
    white = (255, 255, 255)        # 白色
    dark_gray = (64, 64, 64)       # 深灰色
    light_gray = (128, 128, 128)   # 浅灰色
    green = (0, 180, 0)            # 绿色（下载箭头）
    
    # 计算尺寸比例
    center = size // 2
    radius = size // 3
    
    # 1. 绘制圆形背景（深灰色）
    margin = size // 10
    bg_radius = size // 2 - margin
    draw.ellipse([margin, margin, size - margin, size - margin], 
                 fill=dark_gray, outline=light_gray, width=2)
    
    # 2. 绘制YouTube播放按钮（红色三角形背景）
    play_size = size // 4
    play_left = center - play_size // 2
    play_top = center - play_size // 2 - size // 8
    play_right = play_left + play_size
    play_bottom = play_top + play_size
    
    # 绘制YouTube红色圆角矩形
    draw.rounded_rectangle([play_left, play_top, play_right, play_bottom],
                          radius=play_size//6, fill=youtube_red)
    
    # 3. 绘制播放三角形（白色）
    triangle_size = play_size // 2
    triangle_offset = triangle_size // 4
    triangle_center_x = play_left + play_size // 2 + triangle_offset // 2
    triangle_center_y = play_top + play_size // 2
    
    triangle_points = [
        (triangle_center_x - triangle_size//2, triangle_center_y - triangle_size//2),
        (triangle_center_x - triangle_size//2, triangle_center_y + triangle_size//2),
        (triangle_center_x + triangle_size//2, triangle_center_y)
    ]
    draw.polygon(triangle_points, fill=white)
    
    # 4. 绘制下载箭头（绿色）
    arrow_size = size // 5
    arrow_x = center
    arrow_y = center + size // 6
    arrow_thickness = max(2, size // 20)
    
    # 箭头竖线
    line_top = arrow_y - arrow_size // 2
    line_bottom = arrow_y + arrow_size // 3
    draw.rectangle([arrow_x - arrow_thickness//2, line_top, 
                   arrow_x + arrow_thickness//2, line_bottom], fill=green)
    
    # 箭头头部
    arrow_head_size = arrow_size // 3
    arrow_head_points = [
        (arrow_x, line_bottom + arrow_head_size//2),
        (arrow_x - arrow_head_size//2, line_bottom - arrow_head_size//4),
        (arrow_x + arrow_head_size//2, line_bottom - arrow_head_size//4)
    ]
    draw.polygon(arrow_head_points, fill=green)
    
    # 5. 添加下载底线（表示文件）
    bottom_line_y = arrow_y + arrow_size // 2 + arrow_thickness
    bottom_line_width = arrow_size
    draw.rectangle([arrow_x - bottom_line_width//2, bottom_line_y,
                   arrow_x + bottom_line_width//2, bottom_line_y + arrow_thickness],
                   fill=green)
    
    # 保存图像
    try:
        img.save(output_path, format='PNG')
        return True
    except Exception as e:
        print(f"保存图标失败: {e}")
        return False

def create_all_icon_sizes():
    """创建所有尺寸的图标"""
    if not PIL_AVAILABLE:
        print("错误：需要安装Pillow库")
        print("请运行：pip install Pillow")
        return False
    
    base_dir = Path(__file__).parent
    icons_dir = base_dir / "icons"
    icons_dir.mkdir(exist_ok=True)
    
    # Windows ICO 标准尺寸
    sizes = [16, 24, 32, 48, 64, 96, 128, 256]
    
    print("正在创建YouTube下载工具图标...")
    print("=" * 40)
    
    success_count = 0
    png_files = []
    
    for size in sizes:
        output_path = icons_dir / f"icon_{size}x{size}.png"
        if create_youtube_downloader_icon(size, output_path):
            print(f"[OK] 创建 {size}x{size} PNG 图标成功")
            png_files.append(str(output_path))
            success_count += 1
        else:
            print(f"[FAIL] 创建 {size}x{size} PNG 图标失败")
    
    if success_count > 0:
        # 创建ICO文件（包含多个尺寸）
        try:
            ico_path = icons_dir / "app_icon.ico"
            # 使用最大的PNG作为主图标，然后添加其他尺寸
            if png_files:
                main_img = Image.open(png_files[-1])  # 使用最大尺寸
                
                # 收集所有尺寸的图像
                ico_images = []
                for png_file in png_files:
                    img = Image.open(png_file)
                    ico_images.append(img)
                
                # 保存为ICO格式，包含多个尺寸
                main_img.save(ico_path, format='ICO', sizes=[(img.width, img.height) for img in ico_images])
                print(f"[OK] 创建多尺寸ICO图标成功: {ico_path}")
                
                # 创建主PNG图标（256x256）
                main_png = icons_dir / "app_icon.png"
                if (icons_dir / "icon_256x256.png").exists():
                    Image.open(icons_dir / "icon_256x256.png").save(main_png)
                    print(f"[OK] 创建主PNG图标成功: {main_png}")
                
        except Exception as e:
            print(f"✗ 创建ICO文件失败: {e}")
    
    print("=" * 40)
    print(f"图标创建完成！成功创建 {success_count}/{len(sizes)} 个尺寸")
    print(f"图标文件位置: {icons_dir}")
    
    return success_count > 0

def main():
    """主函数"""
    print("[ICON] YT-DLP GUI Windows 图标生成器")
    print("设计特色：YouTube红色主题 + 绿色下载箭头 + 现代化圆形设计")
    print()
    
    if create_all_icon_sizes():
        print()
        print("[SUCCESS] 图标创建成功！")
        print("[INFO] 图标文件已保存到 icons/ 目录")
        print("[INFO] 可以开始打包带图标的应用程序了")
    else:
        print()
        print("[ERROR] 图标创建失败")
        print("[INFO] 请检查是否已安装Pillow库：pip install Pillow")

if __name__ == "__main__":
    main()