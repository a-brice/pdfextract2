import fitz
import numpy as np
import os
from PIL import Image
import time
import logging
import pathlib

def convert_to_img(template_dir, filename, dpi=180, page_to_convert=None):

    img_path = os.path.join(template_dir, 'pages')
    if not os.path.exists(img_path):
        os.mkdir(img_path)

    # for images file (png, jpg)
    if filename.rsplit('.', 1)[1].lower() != 'pdf':
        img = Image.open(os.path.join(template_dir, filename))
        img.save(os.path.join(img_path, f'{filename.rsplit(".", 1)[0]}_$p#0.png'))
        return 1 # nb_pages = 1 since it's an image
    
    # for pdf file
    doc = fitz.open(os.path.join(template_dir, filename))
    nb_pages = doc.page_count
    pages = range(nb_pages) if not page_to_convert else set(page_to_convert)

    for no_page in pages:
        page = doc.load_page(no_page)
        px = page.get_pixmap(dpi=dpi)
        name = filename.rsplit('.', 1)[0]
        px.save(os.path.join(img_path, f'{name}_$p#{no_page}.png'))
    doc.close()

    return nb_pages


def extract_box(path, config):
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        filename=f'logs/extration-{pathlib.Path(path).stem}-{time.time():.0f}.log', 
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
        format="{asctime} - {levelname} - {message}",
        level=logging.INFO
    )
    
    doc = fitz.open(path)
    logging.info(f"Document loaded | path = {path} -> starting extraction")
    drawing = config['drawing']
    dpi = config['dpi']
    baseDPI = 72.0
    zoom = dpi / baseDPI

    all_infos = []
    for no_page in range(doc.page_count):
        page = doc[no_page]
        infos = {}

        # Logging info 
        progress = no_page / doc.page_count
        coef = doc.page_count // 50
        if doc.page_count >= 100 and no_page % (doc.page_count // coef) == 0:
            logging.info(f'In progress : {progress:.3%} done')


        for i in range(len(drawing)):
            try:
                box = (np.array(drawing[i]['bbox']) / zoom).tolist()
                page.set_cropbox(box)
                info = page.get_text().strip()
                infos[drawing[i]['label']] = info
            except:
                infos[drawing[i]['label']] = 'EXCEPTION ERROR'
                logging.warning(f"Exception raised in page n°{no_page} for label:{drawing[i]['label']}!")
        all_infos.append(infos)
    
    logging.info(f"End of extraction")

    return all_infos


def get_next_id(upload_folder):

    list_folder = [int(x) for x in os.listdir(upload_folder) if x.isnumeric()]
    if not list_folder:
        return 1
    return max(list_folder) + 1


def get_page(directory, page, complete_path=True):
    file_list = os.listdir(directory)
    pagename = [x for x in file_list if f'_$p#{page}.png' in x]

    return os.path.join(directory, pagename[0]) if complete_path else pagename[0]




def occurence_dict(dic):
    
    keys = np.array([x['label'] for x in dic])
    keys, counts = np.unique(keys, return_counts=True)
    idx = np.where(counts > 1)[0]
    dupl_keys = dict(zip(keys[idx], np.zeros(idx.shape, np.int32)))
    for x in dic:
        if x['label'] in dupl_keys.keys():
            dupl_keys[x["label"]] += 1
            x['label'] = x['label'] + f'_{dupl_keys[x["label"]]}'
            
    return dic

def gen_dirnames(dirname:str, dirnames: dict):
    """Ensure there is no directory with the same names if there have multiple files with the same name"""
    if dirname in dirnames:
        dirnames[dirname] += 1
        return dirname + f'_{dirnames[dirname]}', dirnames
    else:
        dirnames[dirname] = 0
        return dirname, dirnames