import sys
import os
from markdown2 import markdown
from weasyprint import HTML, CSS

def render_weasy(input_path, output_path, font_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    html_content = markdown(content, extras=['tables', 'fenced-code-blocks', 'cuddled-lists', 'task_list'])
    
    css_string = f"""
        @font-face {{
            font-family: 'B-Nazanin-Local';
            src: url('file://{font_path}');
        }}
        @page {{
            size: A4;
            margin: 20mm;
        }}
        body {{
            font-family: 'B-Nazanin-Local', 'Times New Roman', serif;
            direction: rtl;
            text-align: right;
            font-size: 14pt;
            line-height: 1.6;
            color: #333;
        }}
        h1, h2, h3 {{ 
            color: #000; 
            border-bottom: 2px solid #EEE; 
            padding-bottom: 10px;
            page-break-after: avoid;
        }}
        p, blockquote, pre, table, li, tr {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            direction: rtl;
            margin-bottom: 20px;
        }}
        th, td {{ 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: right; 
        }}
    """
    
    full_html = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="fa">
        <head>
            <meta charset="UTF-8">
        </head>
        <body>
            {html_content}
        </body>
        </html>
    """
    
    HTML(string=full_html).write_pdf(
        output_path, 
        stylesheets=[CSS(string=css_string)]
    )

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
        
    in_md = sys.argv[1]
    out_pdf = sys.argv[2]
    f_path = sys.argv[3] if len(sys.argv) > 3 else "/Library/Fonts/B-NAZANIN.TTF"
    
    render_weasy(in_md, out_pdf, f_path)
