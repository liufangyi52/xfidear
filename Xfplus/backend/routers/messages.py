import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.models import (
    DispatchMessage,
    MessageCreate,
    MessageForwardRequest,
    MessageReviewRequest,
    PublicSuggestionCreate,
    UserPublic,
)
from backend.permissions import require_admin_role
from backend.services.auth_service import current_user
from backend.services.message_service import (
    cancel_public_suggestion,
    create_message,
    create_public_suggestion,
    forward_rectification,
    get_visible_message,
    review_message,
    update_message_attachments,
    visible_messages,
)

router = APIRouter(prefix="/api/messages", tags=["messages"])
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "message_uploads"
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


@router.post("", response_model=DispatchMessage)
def create(payload: MessageCreate, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    return create_message(user, payload)


@router.get("/inbox")
def inbox(
    district: str | None = Query(default=None),
    community: str | None = Query(default=None),
    user: UserPublic = Depends(current_user),
):
    return visible_messages(user, district=district, community=community)


@router.post("/suggestions", response_model=DispatchMessage)
def submit_suggestion(payload: PublicSuggestionCreate, user: UserPublic = Depends(current_user)):
    return create_public_suggestion(
        user,
        title=payload.title,
        content=payload.content,
        district=payload.district,
        community=payload.community,
    )


@router.post("/suggestions/upload", response_model=DispatchMessage)
async def submit_suggestion_with_files(
    title: str = Form(...),
    content: str = Form(...),
    district: str | None = Form(default=None),
    community: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    user: UserPublic = Depends(current_user),
):
    message = create_public_suggestion(user, title=title, content=content, district=district, community=community)
    if not files:
        return message

    message_dir = UPLOAD_DIR / str(message.id)
    message_dir.mkdir(parents=True, exist_ok=True)
    attachments = []
    for upload in files[:5]:
        original_name = Path(upload.filename or "attachment").name
        suffix = Path(original_name).suffix[:16]
        attachment_id = uuid.uuid4().hex
        stored_name = f"{attachment_id}{suffix}"
        target = message_dir / stored_name
        size = 0
        with target.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_ATTACHMENT_SIZE:
                    output.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File is too large")
                output.write(chunk)
        attachments.append(
            {
                "id": attachment_id,
                "name": original_name,
                "size": size,
                "content_type": upload.content_type or "application/octet-stream",
                "stored_name": stored_name,
                "url": f"/api/messages/{message.id}/attachments/{attachment_id}",
            }
        )
        await upload.close()
    return update_message_attachments(message.id, attachments)


@router.get("/{message_id}/attachments/{attachment_id}")
def download_attachment(message_id: int, attachment_id: str, user: UserPublic = Depends(current_user)):
    message = get_visible_message(user, message_id)
    attachment = next((item for item in message.get("attachments", []) if item.get("id") == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    stored_name = Path(attachment.get("stored_name") or "").name
    file_path = UPLOAD_DIR / str(message_id) / stored_name
    if not stored_name or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(
        file_path,
        media_type=attachment.get("content_type") or "application/octet-stream",
        filename=attachment.get("name") or stored_name,
    )


@router.post("/{message_id}/review", response_model=DispatchMessage)
def review(message_id: int, payload: MessageReviewRequest, user: UserPublic = Depends(current_user)):
    return review_message(
        user,
        message_id=message_id,
        status=payload.status,
        reply_content=payload.reply_content,
        review_note=payload.review_note,
    )


@router.post("/{message_id}/forward-rectification", response_model=DispatchMessage)
def forward(message_id: int, payload: MessageForwardRequest, user: UserPublic = Depends(current_user)):
    return forward_rectification(
        user,
        message_id,
        MessageCreate(
            title=payload.title,
            content=payload.content,
            target_roles=payload.target_roles,
            target_district=payload.target_district,
            target_community=payload.target_community,
        ),
    )


@router.post("/{message_id}/cancel", response_model=DispatchMessage)
def cancel(message_id: int, user: UserPublic = Depends(current_user)):
    return cancel_public_suggestion(user, message_id)
