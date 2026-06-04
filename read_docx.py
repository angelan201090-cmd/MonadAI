#!/usr/bin/env python3
import sys
import zipfile
import xml.etree.ElementTree as ET

def read_docx(docx_path):
    try:
        with zipfile.ZipFile(docx_path) as docx:
            tree = ET.fromstring(docx.read('word/document.xml'))
            namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text = []
            for paragraph in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                p_text = ''.join(node.text for node in paragraph.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text)
                if p_text:
                    text.append(p_text)
            return '\n'.join(text)
    except Exception as e:
        return f"Ошибка чтения docx: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Укажите путь к файлу docx")
        sys.exit(1)
    print(read_docx(sys.argv[1]))
