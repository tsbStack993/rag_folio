import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

SUBJECTS = [
    ("Embedded System", "embedded-system", "vec_embedded_system", "Microcontrollers, RTOS, and hardware interfaces."),
    ("Cloud Technology", "cloud-technology", "vec_cloud_technology", "Distributed systems, Docker, K8s, and cloud providers."),
    ("Digital Image Processing", "digital-image-processing", "vec_digital_image_processing", "Filtering, Fourier, and spatial transforms."),
    ("Digital Signal Processing", "digital-signal-processing", "vec_digital_signal_processing", "Signals, FFT, DFT, Z-transforms, and filter design."),
    ("Software Engineering", "software-engineering", "vec_software_engineering", "System design, SDLC, software architecture, and patterns.")
]

def seed():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for name, slug, vec_col, desc in SUBJECTS:
                cur.execute("""
                    INSERT INTO subjects (name, slug, vector_collection_name, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (slug) DO NOTHING;
                """, (name, slug, vec_col, desc))
            conn.commit()
    print("Successfully seeded all 5 subjects into Neon PostgreSQL!")

if __name__ == "__main__":
    seed()
