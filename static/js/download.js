
let dload = document.querySelector('.icon.download');
let req; 

function getDrawing(){
    let rectPos = [];
    let rects = document.querySelectorAll('.rect-box');
    rects.forEach((e) => {
        let attrs = {
            label:e.getAttribute('label'),
            bbox:e.getAttribute('bbox'),
            page:e.getAttribute('page')        
        }
        rectPos.push(attrs);
    })
    return (rectPos)
}


dload.onclick = () => {
    let drawing = getDrawing();
    let config = {
        dpi: dpi,
        drawing: drawing
    }

    req = fetch(urlSave, {
        method: 'POST',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
        body: JSON.stringify(config)
    }).then(res => {
        if (res.ok){            
            location.href = urlDload;
        }
        else{
            alert("Config could not be uploaded ! ");
        }
    });
}