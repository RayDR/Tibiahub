import sys
import os
from datetime import datetime, timedelta

# Add the current directory to sys.path so we can import the app
sys.path.append(os.getcwd())

from app.db.database import SessionLocal, init_db
from app.models.user import User
from app.models.guild import Announcement, Event, AnnouncementType, EventType
from app.core.security import get_password_hash

def seed_data():
    db = SessionLocal()
    
    # Check if admin user exists
    admin_user = db.query(User).filter(User.username == "Admin").first()
    if not admin_user:
        print("Creating Admin user...")
        admin_user = User(
            username="Admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
            guild_rank="Leader",
            tibia_character_name="Admin Char",
            join_date=datetime.utcnow()
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    else:
        print("Admin user already exists.")

    # Create Raffle Announcement
    raffle = db.query(Announcement).filter(Announcement.title == "CONCURSO 1: RIFA DE 5KK").first()
    if not raffle:
        print("Creating Raffle Announcement...")
        raffle = Announcement(
            title="CONCURSO 1: RIFA DE 5KK",
            content="""Premio: 5,000,000 de gold (5kk)
            
Participantes: Todos los miembros activos de la guild pueden participar.

Mecánica:
- Cada jugador recibe un solo número de rifa.
- Los números se asignan en orden de inscripción.
- El sorteo se realizará de forma pública usando un método aleatorio verificable (random).

Fecha y hora del sorteo: Viernes 23 a las 10:00 PM (hora del servidor)

Reglas:
- Solo un número por jugador.
- No se permiten personajes alternos (makers).
- Si el ganador no está conectado al momento del sorteo, el premio se guardará hasta que lo reclame.""",
            type=AnnouncementType.CONTEST,
            author_id=admin_user.id
        )
        db.add(raffle)

    # Create Recruitment Contest Announcement
    recruitment_contest = db.query(Announcement).filter(Announcement.title == "CONCURSO 2: TORNEO DE RECLUTAMIENTO").first()
    if not recruitment_contest:
        print("Creating Recruitment Contest Announcement...")
        recruitment_contest = Announcement(
            title="CONCURSO 2: TORNEO DE RECLUTAMIENTO",
            content="""Premio: 250 Tibia Coins (250 TCs)

Duración:
- Inicio: Desde el anuncio del concurso
- Fin: 1 de febrero

Objetivo: Gana el jugador que reclute la mayor cantidad de personas nuevas a la guild.

Reclutas válidos:
- Personaje nuevo en la guild.
- No haber pertenecido previamente a la guild.
- No ser personaje alterno (maker).
- Permanecer en la guild por un periodo mínimo razonable.

Registro: El reclutador debe reportar cada recluta en la sección de Reclutamiento.

Ganador: El jugador con mayor número de reclutas válidos.
En caso de empate: Gana quien haya reclutado primero o sorteo.""",
            type=AnnouncementType.CONTEST,
            author_id=admin_user.id
        )
        db.add(recruitment_contest)

    # Create Example Event
    event = db.query(Event).filter(Event.title == "Team Hunt: Library").first()
    if not event:
        print("Creating Example Event...")
        event = Event(
            title="Team Hunt: Library",
            description="Looking for EK and ED 400+ for Library hunt. Split loot.",
            start_time=datetime.utcnow() + timedelta(days=1),
            type=EventType.HUNT,
            author_id=admin_user.id
        )
        db.add(event)

    db.commit()
    print("Seeding completed successfully!")
    db.close()

if __name__ == "__main__":
    seed_data()
