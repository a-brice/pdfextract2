import os
from flask import Flask
from flask import url_for, render_template, request, redirect, send_from_directory, Response
from werkzeug.utils import secure_filename
import time
import json

import utils
import pandas as pd
import glob
import shutil
import pathlib 


app = Flask('extractor')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DRAWING_FOLDER'] = os.path.join('uploads', 'by_drawing')
app.config['TEMP_FOLDER'] = os.path.join('uploads', 'temp')
app.config['CONF_FOLDER'] = os.path.join('uploads', 'with_config')

if not os.path.exists(app.config['DRAWING_FOLDER']):
    os.makedirs(app.config['DRAWING_FOLDER'])

if not os.path.exists(app.config['TEMP_FOLDER']):
    os.makedirs(app.config['TEMP_FOLDER'])

if not os.path.exists(app.config['CONF_FOLDER']):
    os.makedirs(app.config['CONF_FOLDER'])


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/template-choice')
def template_choice():
    return render_template('template_choice.html')



@app.route('/draw/', methods=['GET', 'POST', 'PUT'])
def get_drawing():

    if request.method == 'PUT': 
        dpi = request.form.get('dpi')
        sess_id = request.form.get('sess_id')
        assert dpi and sess_id and dpi.isnumeric() and sess_id.isnumeric(), "either dpi or id is not numeric"
        
        template_dir = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id), 'template_pdf')
        assert os.path.exists(template_dir), "template directory not found"
        
        filenames = [x for x in os.listdir(template_dir) if '.pdf' in x]
        assert len(filenames) != 0, "template does not exist"

        max_page = utils.convert_to_img(template_dir, filenames[0], dpi=int(dpi))

        return Response('OK', 200)
    
    if request.method != 'POST' or not request.files.get('template'):
        return redirect(url_for('index'))
    
    sess_id = utils.get_next_id(app.config['DRAWING_FOLDER']) 
    template_dir = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id), 'template_pdf')
    
    # create the directory
    os.makedirs(template_dir)

    # save the template file 
    template = request.files.get('template')
    filename = secure_filename(template.filename)
    template.save(os.path.join(template_dir, filename))

    # create img from template file  
    dpi = 180
    max_page = utils.convert_to_img(template_dir, filename, dpi=dpi)
    
    return render_template('drawing.html', sess_id=sess_id, max_page=max_page, page=0, dpi=dpi)


@app.route('/media/<sess_id>')
@app.route('/media/<sess_id>/<page>')
def get_media(sess_id, page=0):
    upload_folder = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id), 'template_pdf', 'pages')
    return send_from_directory(
        upload_folder,
        utils.get_page(upload_folder, page, False), 
        as_attachment=True
    )

@app.route('/<sess_id>/drawing/save', methods=['POST'])
def save_drawing(sess_id):
    upload_folder = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id))
    filepath = os.path.join(upload_folder, 'drawing.json')

    if not os.path.exists(upload_folder):
        return Response('The sess_id path does not exist', status=400)

    with open(filepath, 'w', encoding='utf-8') as f:
        config = request.json
        config['drawing'] = [
            {k:(eval(v) if k in ['page', 'bbox'] else v) for k,v in x.items()} 
            for x in config['drawing']
        ]
        config['drawing'] = utils.occurence_dict(config['drawing'])
        json.dump(config, f)
        
    
    return Response('OK', status=200)


@app.route('/<sess_id>/drawing/download')
def download_drawing(sess_id):
    upload_folder = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id))
    filepath = os.path.join(upload_folder, 'drawing.json')
    
    if not os.path.exists(filepath):
        return Response('The config file has not be saved', status=400)

    return send_from_directory(
        upload_folder,
        'drawing.json', 
        as_attachment=True
    )


@app.route('/<sess_id>/result/<type>/download')
@app.route('/result/<type>/download')
def download_result(sess_id=None, type='CSV'):
    if sess_id == 'temp':
        upload_folder = os.path.join(app.config['TEMP_FOLDER'])
    elif sess_id is not None:
        upload_folder = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id))
    else:
        sess_id = request.args.get('sess_id')
        assert sess_id != '', 'Session id is mandatory'
        upload_folder = os.path.join(app.config['CONF_FOLDER'], str(sess_id))
    
    res_folder = os.path.join(upload_folder, 'results')
    if type == 'CSV':
        filenames = [x for x in os.listdir(res_folder) if 'result.csv' in x]
        if len(filenames) == 1:
            upload_folder = res_folder
            filename = filenames[0]
        else:
            shutil.make_archive(res_folder, 'zip', res_folder)
            filename = 'results.zip'
    else:
        upload_folder = res_folder
        filename = 'result.json'

    if not os.path.exists(os.path.join(upload_folder, filename)):
        return Response('The result file has not be created', status=400)

    return send_from_directory(
        upload_folder,
        filename, 
        as_attachment=True
    )


@app.route('/pdf/<sess_id>/extract')
def get_test_pdf(sess_id):
    return render_template('pdf_to_convert.html', sess_id=sess_id)


def save_result(dirpath, infos):
    result_path = os.path.join(dirpath, 'results')

    if not os.path.exists(result_path):
        os.makedirs(result_path)


    with open(os.path.join(result_path, 'result.json'), 'w', encoding='utf-8') as file:
        json.dump(infos, file, ensure_ascii=False)

    for file in infos.keys():
        df = pd.DataFrame.from_dict(infos[file])
        name = file.replace('.pdf', '').replace('.PDF', '')
        df.to_csv(os.path.join(result_path, name + '_result.csv'), sep=';', index=False)
    


@app.route('/extraction/', methods=['POST'])
def extraction():

    if not request.form.get('sess_id') or len(request.files) == 0:
        return Response('Bad request', 400)
    
    sess_id = request.form.get('sess_id')
    upload_folder = os.path.join(app.config['DRAWING_FOLDER'], str(sess_id))
    testdir = os.path.join(upload_folder, 'test_pdf')
    
    if not os.path.exists(testdir):
        os.mkdir(testdir)

    with open(os.path.join(upload_folder, 'drawing.json'), 'r', encoding='utf-8') as json_file:
        config = json.load(json_file)
        pages = set([x['page'] for x in config['drawing']])

    all_pdf_infos = {}

    for file in request.files.getlist('pdfs[]'):
        filename = secure_filename(file.filename)
        test_path = os.path.join(testdir, filename)
        file.save(test_path)
        infos = utils.extract_box(test_path, config)
            
        all_pdf_infos[file.filename] = infos

    save_result(upload_folder, all_pdf_infos)

    return Response('OK', 200)



    

@app.route('/file-choice')
def select_files():
   return render_template('file_choice.html') 


@app.route('/with-config/process', methods=['POST'])
def process_files():
    config = request.files.get('config')
    test_files = request.files.getlist('test')

    sess_id = utils.get_next_id(app.config['CONF_FOLDER'])
    
    upload_folder = os.path.join(app.config['CONF_FOLDER'], str(sess_id))
    test_dir = os.path.join(upload_folder, 'test_pdf')
    os.makedirs(test_dir, exist_ok=True)
    
    # save the drawing (config file)
    config.save(os.path.join(upload_folder, 'drawing.json'))
    with open(os.path.join(upload_folder, 'drawing.json'), 'r', encoding='utf-8') as json_file:
        config = json.load(json_file)
        dpi = config['dpi']
        config['drawing'] = utils.occurence_dict(config['drawing'])
    
    
    # save all files in directory containing their name and convert them to images
    all_pdf_infos = {}

    for file in test_files:
        filename = secure_filename(file.filename)
        test_path = os.path.join(test_dir, filename)
        file.save(test_path)
        infos = utils.extract_box(test_path, config)
        
        all_pdf_infos[file.filename] = infos

    save_result(upload_folder, all_pdf_infos)

    return {'sess_id': sess_id}



if __name__ == '__main__':
    app.run(debug=True) 