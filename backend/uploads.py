"""Authenticated, validated photo storage for the self-contained college demo."""
import io
import re
import secrets
import warnings
from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

MAX_BYTES=10*1024*1024

def normalize_image(raw):
    if not raw: raise HTTPException(400,'Choose a photo to upload.')
    if len(raw)>MAX_BYTES: raise HTTPException(413,'Choose a photo smaller than 10 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as photo:
                if photo.format not in {'JPEG','PNG','WEBP'}: raise HTTPException(400,'Choose a JPEG, PNG or WebP photo.')
                if photo.width*photo.height>25_000_000: raise HTTPException(400,'Choose a photo under 25 megapixels.')
                from PIL import ImageOps
                photo=ImageOps.exif_transpose(photo).convert('RGB')
                photo.thumbnail((2400,2400))
                output=io.BytesIO();photo.save(output,format='JPEG',quality=88)
                return output.getvalue()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise HTTPException(400,'This file is not a readable photo. Choose a JPEG, PNG or WebP image.')

def install_upload_routes(app,db,require_user):
    @app.post('/api/uploads/report-image',status_code=201)
    def upload(request:Request,image:UploadFile=File(...)):
        user=require_user(request)
        data=normalize_image(image.file.read(MAX_BYTES+1))
        identifier=secrets.token_hex(16)
        with db() as conn:
            conn.execute('INSERT INTO report_images(id,uploaded_by,data) VALUES(%s,%s,%s)',(identifier,user['id'],data))
        return {'imageUrl':f'/api/report-images/{identifier}','cloudinaryPublicId':None}

    @app.get('/api/report-images/{identifier}')
    def read(identifier:str,request:Request):
        user=require_user(request)
        if not re.fullmatch('[a-f0-9]{32}',identifier): raise HTTPException(404,'Photo not found.')
        with db() as conn:
            row=conn.execute('SELECT uploaded_by,data FROM report_images WHERE id=%s',(identifier,)).fetchone()
            if not row: raise HTTPException(404,'Photo not found.')
            if row['uploaded_by']!=user['id'] and user['role'] not in {'ADMIN','OFFICER'}:
                url=f'/api/report-images/{identifier}'
                assigned=conn.execute('SELECT id FROM fire_reports WHERE image_url=%s AND ((assigned_team_id IS NULL AND assigned_to=%s) OR assigned_team_id IN (SELECT team_id FROM response_team_members WHERE user_id=%s)) UNION ALL SELECT id FROM conflict_reports WHERE image_url=%s AND ((assigned_team_id IS NULL AND assigned_to=%s) OR assigned_team_id IN (SELECT team_id FROM response_team_members WHERE user_id=%s))',(url,user['id'],user['id'],url,user['id'],user['id'])).fetchone()
                if not assigned: raise HTTPException(403,'You do not have access to this photo.')
        return Response(bytes(row['data']),media_type='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
