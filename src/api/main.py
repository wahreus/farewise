"""FastAPI entry point for FareWise."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated
from mangum import Mangum

from fastapi import (FastAPI,
                     File,
                     HTTPException,
                     Request,
                     UploadFile,
                     status)

from src.api.models import AnalysisResponse
from src.api.service import AnalysisService, FareWiseAnalysisService

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 64 * 1024

class UploadTooLargeError(ValueError):
    """Raised when an uploaded file exceeds the configured limit."""

def save_upload(upload: UploadFile) -> Path:
    """Copy an uploaded CSV to a temporary path with a size limit."""
    total_bytes = 0
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".csv") as temporary_file:
            temporary_path = Path(temporary_file.name)
            while chunk := upload.file.read(UPLOAD_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise UploadTooLargeError
                temporary_file.write(chunk)
        return temporary_path
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def create_app(service: AnalysisService | None = None) -> FastAPI:
    """Create the FareWise API with an injectable analysis service."""
    application = FastAPI(
        title="FareWise API",
        version="0.1.0",
        description=(
            "Upload historical TfL journey data and compare PAYG with "
            "Travelcard-based payment strategies."))
    application.state.analysis_service = service or FareWiseAnalysisService()

    @application.get("/")
    def get_service_information() -> dict[str, str]:
        """Describe the service and its interactive documentation."""
        return {"service": "FareWise API",
                "docs": "/docs",
                "health": "/health/ready"}

    @application.get("/health/live")
    def get_liveness() -> dict[str, str]:
        """Confirm that the API process is running."""
        return {"status": "alive"}

    @application.get("/health/ready")
    def get_readiness(request: Request) -> dict[str, str]:
        """Confirm that FareWise reference data is available."""
        analysis_service: AnalysisService = (
            request.app.state.analysis_service)
        if not analysis_service.is_ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FareWise reference data is unavailable")
        return {"status": "ready"}

    @application.post(
        "/analyses",
        response_model=AnalysisResponse,
        summary="Analyse a TfL journey-history CSV")
    def create_analysis(
            request: Request,
            file: Annotated[
                UploadFile,
                File(description="Raw TfL journey-history CSV")],
            ) -> AnalysisResponse:
        """Run a synchronous FareWise analysis for one uploaded CSV."""
        filename = file.filename or ""
        if Path(filename).suffix.casefold() != ".csv":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="The uploaded file must use the .csv extension")
        temporary_path: Path | None = None
        try:
            temporary_path = save_upload(file)
            analysis_service: AnalysisService = (
                request.app.state.analysis_service)
            return analysis_service.analyze_file(temporary_path)
        except UploadTooLargeError as error:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The uploaded CSV must not exceed 2 MiB") from error
        except (ValueError, KeyError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error)) from error
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FareWise reference data is unavailable") from error
        except OSError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FareWise could not read the uploaded file") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return application

app = create_app()
handler = Mangum(app, lifespan="off")
