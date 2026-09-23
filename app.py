import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import (
    Flask, abort, flash, redirect, render_template, request,
    send_from_directory, session, url_for
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
TZ = ZoneInfo("America/Sao_Paulo")


def now_local():
    return datetime.now(TZ).replace(tzinfo=None)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-railway")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024

raw_db_url = os.getenv("DATABASE_URL", "sqlite:///automation_control.db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "142723")

db = SQLAlchemy(app)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if raw_db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(180), nullable=False)
    details = db.Column(db.Text, nullable=False)
    creation_type = db.Column(db.String(40), nullable=False)
    requester = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(120), nullable=True)

    source_type = db.Column(db.String(20), nullable=False, default="new")  # new | change
    parent_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    parent = db.relationship(
        "Project",
        remote_side=[id],
        backref=db.backref("change_requests", cascade="all, delete-orphan", lazy="dynamic")
    )

    status = db.Column(db.String(30), nullable=False, default="pending")
    stage = db.Column(db.String(80), nullable=False, default="Aguardando aprovação")
    progress = db.Column(db.Integer, nullable=False, default=0)
    admin_notes = db.Column(db.Text, nullable=True)

    manual = db.Column(db.Text, nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    approved_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_local, onupdate=now_local)

    def kind_label(self):
        return "Solicitação de alteração" if self.source_type == "change" else "Nova automação"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_local)
    project = db.relationship("Project", lazy="joined")


def ensure_schema_columns():
    """Small deploy-safe migration for databases created by older project versions."""
    inspector = inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("projects")}
    if "department" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE projects ADD COLUMN department VARCHAR(120)"))


with app.app_context():
    db.create_all()
    ensure_schema_columns()


def notify(title, message, project=None):
    item = Notification(title=title, message=message, project=project)
    db.session.add(item)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def save_upload(file_storage, project):
    if not file_storage or not file_storage.filename:
        return None, None
    safe_name = secure_filename(file_storage.filename)
    if not safe_name:
        safe_name = "arquivo"
    stored_name = f"{project.public_id}_{uuid.uuid4().hex[:10]}_{safe_name}"
    destination = UPLOAD_DIR / stored_name
    file_storage.save(destination)
    return safe_name, stored_name


def delete_project_file(project):
    if project.file_path:
        candidate = UPLOAD_DIR / project.file_path
        if candidate.exists() and candidate.is_file():
            candidate.unlink(missing_ok=True)


@app.template_filter("datetime_br")
def datetime_br(value):
    if not value:
        return "—"
    return value.strftime("%d/%m/%Y às %H:%M")


@app.template_filter("date_br")
def date_br(value):
    if not value:
        return "—"
    return value.strftime("%d/%m/%Y")


@app.get("/")
def index():
    pending = Project.query.filter_by(status="pending").order_by(Project.created_at.desc()).all()
    ongoing = Project.query.filter_by(status="in_progress").order_by(Project.updated_at.desc()).all()
    created = Project.query.filter_by(status="completed", source_type="new").order_by(Project.completed_at.desc()).all()
    return render_template("index.html", pending=pending, ongoing=ongoing, created=created)


@app.post("/solicitacoes")
def create_request():
    name = request.form.get("name", "").strip()
    details = request.form.get("details", "").strip()
    creation_type = request.form.get("creation_type", "").strip()
    requester = request.form.get("requester", "").strip()
    department = request.form.get("department", "").strip()

    if not name or not details or not requester or not department or creation_type not in {"Robô", "Dashboard", "Automação"}:
        flash("Preencha o nome da automação, seu nome, setor, objetivo e selecione um tipo válido.", "error")
        return redirect(url_for("index") + "#solicitacoes")

    project = Project(
        name=name,
        details=details,
        creation_type=creation_type,
        requester=requester[:120],
        department=department[:120],
        status="pending",
        stage="Aguardando aprovação",
        progress=0,
    )
    db.session.add(project)
    db.session.flush()
    notify(
        "Nova solicitação recebida",
        f"{name} foi enviada por {requester} · {department} para aprovação ({creation_type}).",
        project,
    )
    db.session.commit()
    flash("Solicitação enviada. Ela ficará pendente até a aprovação do administrador.", "success")
    return redirect(url_for("index") + "#solicitacoes")


@app.post("/automacoes/<public_id>/alteracao")
def request_change(public_id):
    parent = Project.query.filter_by(public_id=public_id, status="completed", source_type="new").first_or_404()
    details = request.form.get("change_details", "").strip()
    requester = request.form.get("requester", "").strip()
    department = request.form.get("department", "").strip()
    if not details or not requester or not department:
        flash("Informe seu nome, setor e descreva as alterações desejadas.", "error")
        return redirect(url_for("index") + "#criadas")

    change = Project(
        name=f"Alteração — {parent.name}",
        details=details,
        creation_type=parent.creation_type,
        requester=requester[:120],
        department=department[:120],
        source_type="change",
        parent=parent,
        status="pending",
        stage="Aguardando aprovação da alteração",
        progress=0,
    )
    db.session.add(change)
    db.session.flush()
    notify(
        "Alteração solicitada",
        f"{requester} · {department} solicitou uma alteração em {parent.name}. O pedido voltou para a fila de aprovação.",
        change,
    )
    db.session.commit()
    flash("Alteração solicitada. O pedido voltou para a fila de solicitações.", "success")
    return redirect(url_for("index") + "#solicitacoes")


@app.get("/arquivos/<public_id>")
def download_file(public_id):
    project = Project.query.filter_by(public_id=public_id, status="completed", source_type="new").first_or_404()
    if not project.file_path or not (UPLOAD_DIR / project.file_path).exists():
        abort(404)
    return send_from_directory(UPLOAD_DIR, project.file_path, as_attachment=True, download_name=project.file_name)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session.clear()
            session["admin_authenticated"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("Senha administrativa incorreta.", "error")
    return render_template("admin_login.html")


@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    pending = Project.query.filter_by(status="pending").order_by(Project.created_at.asc()).all()
    ongoing = Project.query.filter_by(status="in_progress").order_by(Project.updated_at.desc()).all()
    created = Project.query.filter_by(status="completed", source_type="new").order_by(Project.completed_at.desc()).all()
    rejected = Project.query.filter_by(status="rejected").order_by(Project.updated_at.desc()).limit(30).all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(50).all()
    unread_count = Notification.query.filter_by(is_read=False).count()
    return render_template(
        "admin.html",
        pending=pending,
        ongoing=ongoing,
        created=created,
        rejected=rejected,
        notifications=notifications,
        unread_count=unread_count,
    )


@app.post("/admin/projetos/<int:project_id>/editar")
@admin_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    name = request.form.get("name", "").strip()
    details = request.form.get("details", "").strip()
    creation_type = request.form.get("creation_type", "").strip()
    requester = request.form.get("requester", "").strip()
    department = request.form.get("department", "").strip()
    if not name or not details or not requester or not department or creation_type not in {"Robô", "Dashboard", "Automação"}:
        flash("Preencha os dados do projeto, solicitante e setor corretamente.", "error")
        return redirect(url_for("admin_dashboard"))
    project.name = name[:180]
    project.details = details
    project.creation_type = creation_type
    project.requester = requester[:120]
    project.department = department[:120]
    project.updated_at = now_local()
    db.session.commit()
    flash("Dados da solicitação atualizados.", "success")
    anchor = "#solicitacoes" if project.status == "pending" else "#andamento"
    return redirect(url_for("admin_dashboard") + anchor)


@app.post("/admin/projetos/<int:project_id>/aprovar")
@admin_required
def approve_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.status != "pending":
        flash("Essa solicitação não está pendente.", "error")
        return redirect(url_for("admin_dashboard"))
    project.status = "in_progress"
    project.stage = "Planejamento / análise"
    project.progress = max(project.progress, 5)
    project.approved_at = now_local()
    project.updated_at = now_local()
    db.session.commit()
    flash(f"{project.name} foi aprovada e movida para Em andamento.", "success")
    return redirect(url_for("admin_dashboard") + "#andamento")


@app.post("/admin/projetos/<int:project_id>/rejeitar")
@admin_required
def reject_project(project_id):
    project = Project.query.get_or_404(project_id)
    reason = request.form.get("reason", "").strip()
    project.status = "rejected"
    project.stage = "Solicitação recusada"
    project.admin_notes = reason or project.admin_notes
    project.updated_at = now_local()
    db.session.commit()
    flash("Solicitação recusada.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/projetos/<int:project_id>/atualizar")
@admin_required
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.status != "in_progress":
        flash("Somente automações em andamento podem receber atualização de progresso.", "error")
        return redirect(url_for("admin_dashboard"))

    stage = request.form.get("stage", "").strip()
    notes = request.form.get("admin_notes", "").strip()
    try:
        progress = int(request.form.get("progress", project.progress))
    except ValueError:
        progress = project.progress
    project.progress = max(0, min(99, progress))
    if stage:
        project.stage = stage[:80]
    project.admin_notes = notes or None
    project.updated_at = now_local()
    db.session.commit()
    flash("Progresso atualizado.", "success")
    return redirect(url_for("admin_dashboard") + "#andamento")


@app.post("/admin/projetos/<int:project_id>/concluir")
@admin_required
def complete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.status != "in_progress":
        flash("A automação precisa estar em andamento antes de ser concluída.", "error")
        return redirect(url_for("admin_dashboard"))

    manual = request.form.get("manual", "").strip()
    admin_notes = request.form.get("final_notes", "").strip()
    uploaded = request.files.get("final_file")

    if project.source_type == "new":
        if uploaded and uploaded.filename:
            delete_project_file(project)
            project.file_name, project.file_path = save_upload(uploaded, project)
        project.manual = manual or project.manual
        project.admin_notes = admin_notes or project.admin_notes
        project.status = "completed"
        project.stage = "Concluída"
        project.progress = 100
        project.completed_at = now_local()
        project.updated_at = now_local()
        db.session.commit()
        flash("Automação concluída e publicada em Automações criadas.", "success")
        return redirect(url_for("admin_dashboard") + "#criadas")

    # Solicitação de alteração: atualiza o projeto original e preserva o pedido no histórico.
    parent = project.parent
    if not parent:
        flash("Não foi possível localizar a automação original dessa alteração.", "error")
        return redirect(url_for("admin_dashboard"))

    if uploaded and uploaded.filename:
        delete_project_file(parent)
        parent.file_name, parent.file_path = save_upload(uploaded, parent)
    if manual:
        parent.manual = manual
    parent.admin_notes = admin_notes or parent.admin_notes
    parent.version += 1
    parent.completed_at = now_local()
    parent.updated_at = now_local()

    project.manual = manual or project.manual
    project.admin_notes = admin_notes or project.admin_notes
    project.status = "completed"
    project.stage = "Alteração concluída"
    project.progress = 100
    project.completed_at = now_local()
    project.updated_at = now_local()
    db.session.commit()
    flash(f"Alteração concluída. {parent.name} agora está na versão {parent.version}.", "success")
    return redirect(url_for("admin_dashboard") + "#criadas")


@app.post("/admin/projetos/<int:project_id>/editar-criada")
@admin_required
def edit_created(project_id):
    project = Project.query.get_or_404(project_id)
    if project.status != "completed" or project.source_type != "new":
        abort(400)

    manual = request.form.get("manual", "").strip()
    notes = request.form.get("admin_notes", "").strip()
    uploaded = request.files.get("final_file")
    if uploaded and uploaded.filename:
        delete_project_file(project)
        project.file_name, project.file_path = save_upload(uploaded, project)
    project.manual = manual or None
    project.admin_notes = notes or None
    project.updated_at = now_local()
    db.session.commit()
    flash("Automação criada atualizada.", "success")
    return redirect(url_for("admin_dashboard") + "#criadas")


@app.post("/admin/projetos/<int:project_id>/excluir")
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.source_type == "new":
        delete_project_file(project)
    db.session.delete(project)
    db.session.commit()
    flash("Registro excluído.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/notificacoes/<int:notification_id>/ler")
@admin_required
def read_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    notification.is_read = True
    db.session.commit()
    return redirect(url_for("admin_dashboard") + "#notificacoes")


@app.post("/admin/notificacoes/ler-todas")
@admin_required
def read_all_notifications():
    Notification.query.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    flash("Notificações marcadas como lidas.", "success")
    return redirect(url_for("admin_dashboard") + "#notificacoes")


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.errorhandler(413)
def too_large(error):
    flash(f"Arquivo muito grande. O limite atual é {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB.", "error")
    return redirect(request.referrer or url_for("index")), 413


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
