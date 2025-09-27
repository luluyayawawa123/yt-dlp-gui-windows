#!/usr/bin/env python3
"""
测试标题提取逻辑
"""

import sys
import os
from pathlib import Path
import urllib.parse as urlparse

# 将src目录添加到Python路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from core.downloader import Downloader
import logging

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def extract_title_from_destination(destination_line):
    """从Destination行提取标题"""
    dest_index = destination_line.find('Destination:')
    if dest_index != -1:
        # 从"Destination:"之后提取内容
        title_part = destination_line[dest_index + len('Destination:'):].strip()
        # 移除可能的额外信息（如进度信息）
        # 按顺序处理各种可能的进度信息分隔符
        progress_separators = [' [download]', ' ETA ', ' at ', ' of ']
        for separator in progress_separators:
            if separator in title_part:
                title_part = title_part.split(separator)[0]
        
        # 进一步清理可能的数字和百分比信息
        import re
        # 移除类似 "0.0%" 的百分比信息
        title_part = re.sub(r'\s*\d+\.\d+%\s*.*$', '', title_part)
        # 移除类似 ".f123" 的临时文件扩展名
        title_part = re.sub(r'\.f\d+', '', title_part)
        
        # 检查是否是字幕文件，如果是则跳过（我们只关心视频文件的标题）
        subtitle_extensions = ['.vtt', '.srt', '.ass', '.lrc', '.sbv', '.sub', '.txt']
        is_subtitle_file = any(ext in title_part for ext in subtitle_extensions)
        if is_subtitle_file:
            return ""
        
        title = os.path.splitext(os.path.basename(title_part))[0]
        return title
    return ""

def validate_title(title):
    """验证标题是否合理"""
    if not title or len(title) <= 1:
        return False
    
    # 对于非常短的标题（如"s"），需要额外验证
    if len(title) <= 3:
        # 检查是否是合理的标题（不是纯数字或特殊字符）
        is_valid_title = not title.replace('.', '').replace('_', '').replace('-', '').isdigit()
        # 如果是单个字母，很可能是错误的标题
        if len(title) == 1 and title.isalpha():
            is_valid_title = False
        return is_valid_title
    
    return True

def extract_title_from_url(url):
    """从URL中提取标题"""
    try:
        parsed_url = urlparse.urlparse(url)
        # 对于YouTube链接
        if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
            if 'v=' in parsed_url.query:
                video_id = urlparse.parse_qs(parsed_url.query)['v'][0]
                return f"YouTube视频_{video_id}"
            elif 'youtu.be' in parsed_url.netloc:
                video_id = parsed_url.path.lstrip('/')
                return f"YouTube视频_{video_id}"
        # 对于小红书链接
        elif 'xiaohongshu.com' in parsed_url.netloc:
            # 提取视频ID
            path_parts = parsed_url.path.strip('/').split('/')
            if path_parts and path_parts[-1]:
                return f"小红书视频_{path_parts[-1][:10]}"  # 取前10个字符
            else:
                return "小红书视频"
        # 对于其他平台，使用域名和路径信息
        else:
            path_parts = parsed_url.path.strip('/').split('/')
            if path_parts and path_parts[-1]:
                # 限制标题长度
                domain_part = parsed_url.netloc.split('.')[0]  # 取域名的主要部分
                path_part = path_parts[-1][:20]  # 限制路径部分长度
                return f"{domain_part}_{path_part}"
            else:
                return parsed_url.netloc
    except:
        return url

def test_title_extraction():
    """测试标题提取逻辑"""
    # 模拟一些可能的yt-dlp输出
    test_cases = [
        ("[download] Destination: test_video.mp4", "https://www.youtube.com/watch?v=abc123"),
        ("[download] Destination: video_with_spaces.mp4 ETA 00:02:30", "https://www.xiaohongshu.com/explore/xyz789"),
        ("[download] Destination: s ETA 02:02:05", "https://www.youtube.com/watch?v=def456"),
        ("[download] Destination: My Video Title.mp4", "https://example.com/video/123"),
        ("[download] Destination: short.mp4 at 2.5MiB/s", "https://vimeo.com/456789"),
        ("[download] Destination: Vlog：本格的な練習に向けて徐々に体を戻していく1週間Vlog.f397.mp4 [download]   0.0% of   36", "https://www.youtube.com/watch?v=WjPXAwOYkDA&t=46s"),
        ("[download] Destination: Another Test Video.f123.mp4 [download]  23.4% of 50.75MiB at 2.52MiB/s ETA 00:15", "https://www.youtube.com/watch?v=xyz789"),
        ("[download] Destination: 字幕文件测试.en.vtt", "https://www.youtube.com/watch?v=subtitle123"),  # 字幕文件测试
    ]
    
    print("测试标题提取逻辑:")
    print("=" * 50)
    
    for i, (test_case, url) in enumerate(test_cases):
        print(f"\n测试用例 {i+1}: {test_case}")
        print(f"  URL: {url}")
        
        # 提取标题
        title = extract_title_from_destination(test_case)
        print(f"  从Destination提取的标题: '{title}'")
        
        # 验证标题
        if validate_title(title):
            print(f"  标题有效")
        else:
            print(f"  标题无效，尝试从URL提取")
            url_title = extract_title_from_url(url)
            print(f"  从URL提取的标题: '{url_title}'")
            title = url_title

if __name__ == "__main__":
    test_title_extraction()