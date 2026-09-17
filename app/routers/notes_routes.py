from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import models
from app.auth import ROLE_WRITE
from app.database import get_db
from app.web import redirect, require_roles

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
MAX_IMAGE_SIZE = 2 * 1024 * 1024
MAX_IMAGES_PER_NOTE = 3


async def _read_image(img: UploadFile):
    data = await img.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise ValueError(f"La imagen '{img.filename}' supera los 2 MB.")
    if img.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"Formato no permitido en '{img.filename}'. Usá JPG, PNG, WEBP o GIF."
        )
    return data


@router.post("/experimentos/{experiment_id}/notas/crear")
async def create_note(
    experiment_id: int,
    request: Request,
    description: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    user = require_roles(request, ROLE_WRITE)
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        return redirect("/experimentos", error="Experimento no encontrado.")
    description = description.strip()
    if not description:
        return redirect(f"/experimentos/{experiment_id}", error="La descripción no puede estar vacía.")

    images = [i for i in images if i.filename]
    if len(images) > MAX_IMAGES_PER_NOTE:
        return redirect(f"/experimentos/{experiment_id}", error=f"Máximo {MAX_IMAGES_PER_NOTE} imágenes por nota.")

    note = models.Note(
        experiment_id=experiment_id,
        user_id=user["uid"],
        description=description,
    )
    db.add(note)
    db.flush()

    try:
        for img in images:
            data = await _read_image(img)
            db.add(models.NoteImage(
                note_id=note.id,
                data=data,
                content_type=img.content_type,
                filename=img.filename,
            ))
    except ValueError as exc:
        db.rollback()
        return redirect(f"/experimentos/{experiment_id}", error=str(exc))

    db.commit()
    return redirect(f"/experimentos/{experiment_id}", msg="Nota creada.")


@router.post("/notas/{note_id}/editar")
async def edit_note(
    note_id: int,
    request: Request,
    description: str = Form(""),
    images: list[UploadFile] = File(default=[]),
    remove_images: list[int] = Form(default=[]),
    db: Session = Depends(get_db),
):
    user = require_roles(request, ROLE_WRITE)
    note = db.get(models.Note, note_id)
    if note is None:
        return redirect("/experimentos", error="Nota no encontrada.")
    if user["role"] != "admin" and note.user_id != user["uid"]:
        return redirect(
            f"/experimentos/{note.experiment_id}",
            error="No podés editar esta nota.",
        )
    description = description.strip()
    if not description:
        return redirect(f"/experimentos/{note.experiment_id}", error="La descripción no puede estar vacía.")

    for img_id in remove_images:
        img = db.get(models.NoteImage, img_id)
        if img and img.note_id == note.id:
            db.delete(img)

    note.description = description
    db.flush()

    existing_count = (
        db.query(models.NoteImage).filter_by(note_id=note.id).count()
    )
    new_images = [i for i in images if i.filename]
    if existing_count + len(new_images) > MAX_IMAGES_PER_NOTE:
        db.rollback()
        return redirect(
            f"/experimentos/{note.experiment_id}",
            error=f"Una nota puede tener como máximo {MAX_IMAGES_PER_NOTE} imágenes.",
        )

    try:
        for img in new_images:
            data = await _read_image(img)
            db.add(models.NoteImage(
                note_id=note.id,
                data=data,
                content_type=img.content_type,
                filename=img.filename,
            ))
    except ValueError as exc:
        db.rollback()
        return redirect(f"/experimentos/{note.experiment_id}", error=str(exc))

    db.commit()
    return redirect(f"/experimentos/{note.experiment_id}", msg="Nota actualizada.")


@router.post("/notas/{note_id}/eliminar")
def delete_note(note_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_roles(request, ROLE_WRITE)
    note = db.get(models.Note, note_id)
    if note is None:
        return redirect("/experimentos", error="Nota no encontrada.")
    if user["role"] != "admin" and note.user_id != user["uid"]:
        return redirect(
            f"/experimentos/{note.experiment_id}",
            error="No podés eliminar esta nota.",
        )
    exp_id = note.experiment_id
    db.delete(note)
    db.commit()
    return redirect(f"/experimentos/{exp_id}", msg="Nota eliminada.")


@router.get("/notas/{image_id}/imagen")
def note_image(image_id: int, request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    img = db.get(models.NoteImage, image_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return Response(content=img.data, media_type=img.content_type)