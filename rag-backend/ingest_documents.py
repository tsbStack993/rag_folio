"""Load small, editable starter notes into the subject-scoped pgvector table."""

import asyncio
import math
import os
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

load_dotenv(Path(__file__).with_name(".env"))

from rag_service import (
    EMBEDDING_DIMENSIONS,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    vector_literal,
)

CHUNK_MIN_WORDS = 300
CHUNK_MAX_WORDS = 500
CHUNK_OVERLAP_WORDS = 40

STARTER_DOCUMENTS: dict[str, tuple[str, str]] = {
    "embedded-system": (
        "Embedded Systems: Microcontrollers, Real-Time Tasks, and Interfaces",
        """An embedded system combines a processor, memory, input and output circuitry, and software to perform a defined task inside a larger product. Unlike a general-purpose computer, it is usually designed around limits on power, cost, physical size, and response time. A microcontroller integrates a CPU core, flash program memory, SRAM, timers, and peripheral interfaces on one chip. Firmware configures those resources and repeatedly responds to sensors, communication interfaces, and control inputs.

The main loop is a simple design for small systems: read inputs, update application state, and drive outputs. It is easy to understand, but a blocking delay or slow peripheral operation can postpone every other task. Interrupts let hardware notify the processor when an event occurs, such as a timer tick or received byte. An interrupt service routine should remain short: capture the event, move data into a buffer, and return. Long calculations and blocking operations belong in normal task context. Shared data between an interrupt and foreground code needs deliberate synchronization; declaring a variable volatile affects compiler optimizations but does not make multi-step updates atomic.

A real-time system is judged by whether it produces a correct result before its deadline, not simply by its average speed. A hard deadline must never be missed; a soft deadline miss degrades service but may be tolerable. A real-time operating system schedules independent tasks by priority and can provide queues, semaphores, timers, and task notifications. Priority inversion occurs when a high-priority task waits for a resource held by a lower-priority task; priority inheritance and short critical sections reduce this risk. Engineers should budget worst-case execution time and interrupt latency rather than relying only on typical measurements.

Common interfaces include GPIO for digital signals, UART for asynchronous serial communication, SPI for a clocked multi-device bus, and I2C for addressed peripherals using shared clock and data lines. Engineers must check voltage levels, pull-up requirements, clock limits, and framing details in device data sheets. For example, I2C devices share the bus through open-drain outputs and pull-up resistors, while SPI chip-select signals identify the active peripheral. A logic analyzer can reveal timing and protocol errors that are difficult to infer from application logs.

Reliable firmware also accounts for startup state, watchdog recovery, brownouts, and invalid sensor readings. A watchdog should be serviced only after critical work has demonstrably completed, otherwise it can conceal a stalled task. Use explicit units and ranges for sensor values, validate messages before acting on them, and define safe output states for faults. Testing combines host-side unit tests for logic, hardware-in-the-loop checks for peripheral behavior, and longer endurance runs. These practices make the design observable and recoverable instead of merely functional on its first successful boot.""",
    ),
    "cloud-technology": (
        "Cloud Technology: Distributed Applications and Operations",
        """Cloud computing provides on-demand access to configurable compute, storage, and networking resources. In infrastructure as a service, teams manage virtual machines and more of the operating system. Platform services provide a managed runtime or data service, while software as a service delivers a complete application. The shared-responsibility boundary changes with each service: a provider operates the underlying facilities, but customers remain responsible for identity, data classification, configuration, and application behavior.

A cloud application is commonly divided into independently deployable components. Containers package an application with its runtime dependencies, while a container image is an immutable template from which containers are started. Orchestration platforms such as Kubernetes schedule containers onto nodes, restart failed workloads, and expose services through stable network abstractions. A Deployment describes a desired number of interchangeable replicas; a Service provides a consistent endpoint for selected pods. Readiness checks determine whether a replica should receive traffic, while liveness checks can trigger a restart. These checks must measure meaningful application health rather than merely confirming that a process exists.

Distributed systems introduce partial failure: one service can be unavailable while others continue running. Network calls therefore need timeouts, bounded retries, and clear failure handling. Retrying a non-idempotent operation can create duplicate effects, so a client may need an idempotency key or a deduplication record. Exponential backoff with jitter prevents many clients from retrying simultaneously. A circuit breaker can temporarily stop calls to a persistently failing dependency. Queues decouple producers from consumers and absorb bursts, but they also require policies for message ordering, delivery attempts, poison messages, and eventual consistency.

Scalability can be vertical, by giving one instance more resources, or horizontal, by adding instances. Horizontal scaling works best for stateless services; shared session state should live in a suitable external store. Autoscaling policies should use signals related to demand, such as queue depth or sustained resource pressure, and should account for startup time. Capacity planning also includes database connections, storage growth, network limits, and downstream quotas. Adding application replicas without raising a database connection limit can make an overloaded system less reliable.

Cloud security begins with least-privilege identities, short-lived credentials, private networking where practical, encryption in transit and at rest, and managed secret storage. Observability combines structured logs, metrics, and distributed traces so operators can connect a user-visible failure to a specific dependency. Service-level indicators measure outcomes such as request success and latency; service-level objectives set target ranges over a defined period. Backups are useful only when restoration is periodically tested. A deployment plan should include staged rollout, health monitoring, and a rollback path, because a successful image build alone does not demonstrate a safe production release.""",
    ),
    "digital-image-processing": (
        "Digital Image Processing: Sampling, Filtering, and Segmentation",
        """A digital image is a two-dimensional array of sampled intensity or color values. A grayscale image stores one value per pixel; a color image commonly stores red, green, and blue channels. Spatial resolution describes the number of samples, while bit depth determines how many intensity levels can be represented. Increasing resolution does not recover details that were absent during capture. The Nyquist principle states that a sampled signal must be sampled at more than twice its highest frequency to avoid aliasing, assuming appropriate band limitation. In imaging, aliasing can appear as jagged edges or false patterns, so optical or digital low-pass filtering is often applied before downsampling.

Point operations transform each pixel independently. Contrast stretching maps a selected intensity range to a wider display range, and thresholding separates pixels into classes based on intensity. A histogram counts occurrences of intensity values and helps identify underexposure, saturation, or multiple tonal groups. Histogram equalization redistributes intensity levels to improve global contrast, but may amplify noise or change local appearance. Color processing should account for the color space: RGB is convenient for display, whereas HSV or perceptual spaces can make hue or lightness operations easier to interpret.

Spatial filters use a neighborhood around each pixel. Convolution multiplies neighborhood values by a kernel and sums the products. A box filter averages neighboring values and smooths rapid changes, but also blurs edges. A Gaussian kernel assigns greater weight to nearby pixels and is commonly used for noise reduction. Median filtering is nonlinear: it replaces a pixel with the neighborhood median and is effective against isolated salt-and-pepper noise while often preserving edges better than averaging. Kernel size and border handling affect the result, so the implementation should document how pixels beyond the image boundary are treated.

The two-dimensional Fourier transform represents an image in terms of spatial frequencies. Low frequencies describe gradual intensity changes; high frequencies describe fine detail and sharp transitions. Filtering in the frequency domain multiplies the transform by a frequency response and then applies an inverse transform. A low-pass filter suppresses high-frequency noise but can soften edges. A high-pass filter emphasizes detail but may also amplify noise. Frequency-domain work requires care with transform centering, scaling, and boundary artifacts; padding can reduce wraparound effects.

Segmentation partitions an image into regions that share a useful property. Global thresholding is simple when foreground and background intensities are well separated. Adaptive thresholding estimates a local threshold for uneven illumination. Edge methods detect strong spatial derivatives, while region-growing methods expand from seeds using similarity rules. Morphological erosion and dilation operate on binary shapes using a structuring element; opening removes small foreground details and closing fills small gaps. Evaluation should use representative labeled images and measures such as intersection over union, while also inspecting failure cases. Preprocessing, parameter choices, and the definition of a correct boundary all influence measured performance, so results should be reported with the dataset and settings.""",
    ),
    "digital-signal-processing": (
        "Digital Signal Processing: Sampling, Transforms, and Filters",
        """Digital signal processing represents measurements as sequences of numbers and uses algorithms to analyze or modify them. An analog signal is continuous in time; an analog-to-digital converter samples it at a fixed rate and quantizes each sample to a finite set of levels. If the input contains frequencies above half the sampling rate, they can fold into lower frequencies as aliasing. An analog anti-aliasing low-pass filter is therefore used before conversion. Quantization introduces an error between the analog value and its encoded level; greater resolution generally lowers quantization noise but does not eliminate sensor or analog-front-end noise.

Discrete-time signals are indexed by integer sample number. A system is linear if it obeys superposition and time-invariant if shifting the input shifts the output without changing its behavior. For a linear time-invariant system, the output is the convolution of the input with the system's impulse response. A finite impulse response filter has a finite-duration impulse response and can be designed with exact linear phase, at the cost of potentially requiring more coefficients. An infinite impulse response filter uses feedback and can achieve a given selectivity with fewer coefficients, but its phase may be nonlinear and stability must be considered.

The discrete Fourier transform converts a finite block of samples into a set of frequency components. The fast Fourier transform is an efficient family of algorithms for computing the same DFT. The frequency-bin spacing equals the sample rate divided by the number of samples, so a longer observation provides finer bin spacing but assumes the signal is sufficiently stable over that interval. A window such as Hann reduces spectral leakage caused by analyzing a finite segment, though it changes amplitude and bandwidth characteristics. For amplitude measurements, the chosen window's coherent gain and one-sided spectrum scaling should be accounted for.

A z-transform describes discrete-time sequences in a complex variable and supports analysis of poles, zeros, and system stability. For a causal rational system, poles inside the unit circle indicate BIBO stability. The frequency response is evaluated on the unit circle when the region of convergence permits it. Difference equations implement digital filters directly, but fixed-point implementations must account for coefficient precision, accumulator width, overflow, and limit cycles. Floating-point arithmetic simplifies dynamic range management on many processors but still requires numerical validation.

Practical DSP systems also address latency, throughput, and real-time deadlines. Block processing improves computational efficiency but adds buffering delay; sample-by-sample processing can reduce latency but may increase overhead. Test signals such as impulses, steps, sinusoids, and white noise reveal different properties. Compare measured output with an analytical or trusted reference, test boundary conditions, and verify behavior at the intended sample rates and amplitudes. A plotted result is useful, but automated assertions on gain, passband, stopband, stability, and timing make regressions easier to detect.""",
    ),
    "software-engineering": (
        "Software Engineering: Requirements, Design, and Quality",
        """Software engineering applies disciplined methods to building, operating, and evolving software. A lifecycle may include discovery, requirements, design, implementation, verification, release, and maintenance; teams often repeat these activities iteratively rather than completing them once in a strict sequence. Requirements should identify users, observable behavior, constraints, and acceptance criteria. A useful requirement is testable and avoids prescribing implementation details unless they are necessary constraints. Stakeholders should resolve conflicting goals such as security, usability, performance, and delivery time before those conflicts become expensive rework.

Architecture describes major components, their responsibilities, and the rules governing their interactions. A layered design can separate presentation, application logic, and persistence. Modular boundaries should keep related behavior together and limit the knowledge one component needs about another. Interfaces make dependencies explicit and can allow implementations to be replaced in tests. Design patterns are reusable approaches, not mandatory templates: introducing an abstraction is valuable when it reduces coupling or clarifies a changing responsibility, but unnecessary indirection makes a system harder to understand.

Version control records changes and supports collaboration. Small, focused commits make review and regression diagnosis easier. Code review checks correctness, readability, security implications, tests, and compatibility with existing conventions. Automated continuous integration can run formatting, static analysis, unit tests, and builds for every change. A green pipeline provides evidence for the checks it runs, not proof that every possible behavior is correct. Tests should be selected at appropriate boundaries: unit tests isolate small rules, integration tests exercise cooperating components and real persistence or protocols, and end-to-end tests validate representative user journeys.

Maintainability depends on clear names, cohesive functions, controlled complexity, and documentation that explains decisions or operational steps. Refactoring changes internal structure while preserving externally visible behavior; a reliable test suite helps detect accidental behavior changes. Technical debt is the future cost of expedient design choices and should be tracked rather than hidden. Dependencies should be updated thoughtfully, with attention to compatibility, vulnerability advisories, and reproducible builds.

Quality includes more than feature correctness. Reliability concerns operation over time; performance concerns resource use and response time; usability concerns whether users can complete their tasks; security concerns protecting systems and data from misuse. Threat modeling identifies assets, trust boundaries, and plausible abuse cases early enough to influence design. Production observability uses logs, metrics, and traces while avoiding unnecessary sensitive data. Incident response benefits from clear ownership, rollback procedures, backups, and rehearsed recovery. A release is complete only when the software can be monitored, supported, and safely changed. Teams should use defects and incidents to improve process and design, not merely to assign blame.""",
    ),
}


def chunk_text(
    text: str,
    min_words: int = CHUNK_MIN_WORDS,
    max_words: int = CHUNK_MAX_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    if min_words < 1 or max_words < min_words or not 0 <= overlap_words < min_words:
        raise ValueError("Chunk sizes or overlap are invalid")

    words = re.findall(r"\S+", text.strip())
    if not words:
        return []

    if len(words) <= max_words:
        return [" ".join(words)]

    chunk_count = math.ceil(
        (len(words) - overlap_words) / (max_words - overlap_words)
    )
    chunk_size = math.ceil(
        (len(words) + overlap_words * (chunk_count - 1)) / chunk_count
    )
    chunks = []
    for index in range(chunk_count):
        start = index * (chunk_size - overlap_words)
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
    return chunks


async def embed_document(client: httpx.AsyncClient, content: str) -> list[float]:
    response = await client.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": OLLAMA_EMBED_MODEL, "input": content},
    )
    response.raise_for_status()
    payload = response.json()
    embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(embeddings, list) or not embeddings or not isinstance(embeddings[0], list):
        raise ValueError("Ollama returned no document embedding")

    embedding = [float(value) for value in embeddings[0]]
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Ollama returned a {len(embedding)}-dimensional embedding; "
            f"{EMBEDDING_DIMENSIONS} dimensions are required"
        )
    if not all(math.isfinite(value) for value in embedding):
        raise ValueError("Ollama returned a non-finite embedding value")
    return embedding


def upsert_starter_chunk(
    connection: psycopg.Connection[Any],
    columns: set[str],
    chunk_id: Any,
    subject_id: Any,
    content: str,
    title: str,
    page: int,
    embedding: str,
) -> None:
    required_columns = {"id", "subject_id", "content", "embedding", "metadata"}
    missing_columns = required_columns - columns
    if missing_columns:
        raise RuntimeError(
            "subject_document_chunks is missing required columns: "
            + ", ".join(sorted(missing_columns))
            + "; apply db/schema.sql first"
        )

    values_by_column: dict[str, Any] = {
        "id": chunk_id,
        "subject_id": subject_id,
        "content": content,
        "document_title": title,
        "page_number": page,
        "metadata": Jsonb(
            {
                "document_title": title,
                "page_number": page,
                "source": "bundled starter notes",
                "ingestion_key": f"starter:{chunk_id}",
            }
        ),
        "metada": Jsonb(
            {
                "document_title": title,
                "page_number": page,
                "source": "bundled starter notes",
                "ingestion_key": f"starter:{chunk_id}",
            }
        ),
        "rag_metadata": Jsonb(
            {
                "document_title": title,
                "page_number": page,
                "source": "bundled starter notes",
                "ingestion_key": f"starter:{chunk_id}",
            }
        ),
        "embedding": embedding,
    }
    optional_order = (
        "document_title",
        "page_number",
        "metadata",
        "metada",
        "rag_metadata",
    )
    insert_columns = ["id", "subject_id", "content"]
    insert_columns.extend(column for column in optional_order if column in columns)
    insert_columns.append("embedding")
    placeholders = [
        "%s::vector" if column == "embedding" else "%s"
        for column in insert_columns
    ]
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in insert_columns
        if column != "id"
    )
    query = f"""
        INSERT INTO subject_document_chunks ({", ".join(insert_columns)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT (id) DO UPDATE SET {updates}
    """
    connection.execute(query, tuple(values_by_column[column] for column in insert_columns))


async def ingest() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set in rag-backend/.env")

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        subjects = connection.execute(
            "SELECT id, slug FROM subjects WHERE slug = ANY(%s)",
            (list(STARTER_DOCUMENTS),),
        ).fetchall()
    subject_ids = {row["slug"]: row["id"] for row in subjects}
    missing_subjects = set(STARTER_DOCUMENTS) - subject_ids.keys()
    if missing_subjects:
        raise RuntimeError(
            "Seed the subjects before ingestion; missing slugs: "
            + ", ".join(sorted(missing_subjects))
        )

    records = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as ollama:
        for slug, (title, text) in STARTER_DOCUMENTS.items():
            for page, content in enumerate(chunk_text(text), start=1):
                embedding = await embed_document(ollama, content)
                chunk_id = uuid5(NAMESPACE_URL, f"rag-folio-starter:{slug}:{page}")
                records.append(
                    (
                        chunk_id,
                        subject_ids[slug],
                        content,
                        title,
                        page,
                        vector_literal(embedding),
                    )
                )

    with psycopg.connect(database_url) as connection:
        table_columns = {
            row[0]
            for row in connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'subject_document_chunks'
                """
            ).fetchall()
        }
        for chunk_id, subject_id, content, title, page, embedding in records:
            upsert_starter_chunk(
                connection,
                table_columns,
                chunk_id,
                subject_id,
                content,
                title,
                page,
                embedding,
            )
        connection.commit()

    for slug, (title, _) in STARTER_DOCUMENTS.items():
        print(f"Ingested {title} for {slug}")

    chunk_ids = [record[0] for record in records]
    with psycopg.connect(database_url) as connection:
        verified_count = connection.execute(
            """
            SELECT count(*)
            FROM subject_document_chunks
            WHERE id = ANY(%s)
            """,
            (chunk_ids,),
        ).fetchone()[0]

    print(f"Committed {len(records)} starter document chunks.")
    print(f"Verified persisted starter chunk rows: {verified_count}")
    if verified_count != len(records):
        raise RuntimeError(
            f"Expected {len(records)} persisted starter chunks, found {verified_count}"
        )
    return verified_count


if __name__ == "__main__":
    asyncio.run(ingest())
