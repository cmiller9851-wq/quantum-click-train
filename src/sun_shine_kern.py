import io
import struct
import numpy as np
from typing import BinaryIO, Union, Optional, Tuple

# Protocol verification markers (ASCII "PIAN" and "VIOL")
MARKER_PIANO: int = 0x5049414E
MARKER_VIOLIN: int = 0x56494F4C


class WatermarkedLittleEndianWriter:
    """
    Constructs raw byte streams enforcing Little-Endian byte ordering
    with embedded watermark verification headers and piano/violin key signatures.
    """

    __slots__ = ("_buffer", "_watermark")

    def __init__(self, watermark: bytes = b"CRA_PROTOCOL_v2.1"):
        self._buffer = bytearray()
        self._watermark = watermark
        self._write_header()

    def _write_header(self) -> None:
        wm_bytes = self._watermark
        wm_len = len(wm_bytes)
        
        # Header: [WM_LEN (u16)] [WM_BYTES] [PIANO_MARKER (u32)] [VIOLIN_MARKER (u32)]
        self._buffer.extend((wm_len & 0xFFFF).to_bytes(2, byteorder="little"))
        self._buffer.extend(wm_bytes)
        self._buffer.extend(MARKER_PIANO.to_bytes(4, byteorder="little"))
        self._buffer.extend(MARKER_VIOLIN.to_bytes(4, byteorder="little"))

    def write_f64(self, val: float) -> "WatermarkedLittleEndianWriter":
        self._buffer.extend(struct.pack("<d", val))
        return self

    def to_bytes(self) -> bytes:
        return bytes(self._buffer)


class WatermarkedLittleEndianReader:
    """
    Binary reader for Little-Endian streams. Validates watermarks 
    and piano/violin protocol markers before processing stream data.
    """

    __slots__ = ("_stream", "watermark", "piano_key", "violin_key")

    def __init__(self, source: Union[bytes, bytearray, BinaryIO], expected_watermark: Optional[bytes] = None):
        if isinstance(source, (bytes, bytearray)):
            self._stream: BinaryIO = io.BytesIO(source)
        else:
            self._stream = source

        self.watermark: bytes = b""
        self.piano_key: int = 0
        self.violin_key: int = 0

        self._verify_header(expected_watermark)

    def _verify_header(self, expected_watermark: Optional[bytes]) -> None:
        wm_len_data = self._stream.read(2)
        if len(wm_len_data) < 2:
            raise EOFError("Unexpected EOF while parsing header watermark length")
        wm_len = wm_len_data[0] | (wm_len_data[1] << 8)

        self.watermark = self._stream.read(wm_len)
        if len(self.watermark) < wm_len:
            raise EOFError("Unexpected EOF while parsing watermark payload")

        if expected_watermark is not None and self.watermark != expected_watermark:
            raise ValueError(f"Watermark mismatch: expected {expected_watermark!r}, got {self.watermark!r}")

        piano_data = self._stream.read(4)
        violin_data = self._stream.read(4)
        if len(piano_data) < 4 or len(violin_data) < 4:
            raise EOFError("Unexpected EOF while parsing instrument key markers")

        self.piano_key = piano_data[0] | (piano_data[1] << 8) | (piano_data[2] << 16) | (piano_data[3] << 24)
        self.violin_key = violin_data[0] | (violin_data[1] << 8) | (violin_data[2] << 16) | (violin_data[3] << 24)

        if self.piano_key != MARKER_PIANO or self.violin_key != MARKER_VIOLIN:
            raise ValueError("Invalid instrument signature markers in stream header")

    def read_f64(self) -> float:
        data = self._stream.read(8)
        if len(data) < 8:
            raise EOFError("Unexpected EOF while reading f64")
        return struct.unpack("<d", data)[0]


class SolarVectorInput:
    """
    Models physical solar radiation manifold parameters:
      - flux_density: Solar irradiance / spectral flux density (W/m^2)
      - magnetic_vector: 3D magnetic field tensor B = (Bx, By, Bz) in Tesla
      - cycle_frequency: Solar rotational/activity frequency w_c (rad/s)
      - timestamp: Epoch offset t (seconds)
    """

    __slots__ = ("flux_density", "magnetic_vector", "cycle_frequency", "timestamp")

    def __init__(
        self,
        flux_density: float = 1361.0,
        magnetic_vector: Tuple[float, float, float] = (1e-4, 0.0, 5e-5),
        cycle_frequency: float = 2.86e-6,
        timestamp: float = 0.0,
    ):
        self.flux_density = flux_density
        self.magnetic_vector = np.array(magnetic_vector, dtype=float)
        self.cycle_frequency = cycle_frequency
        self.timestamp = timestamp

    def compute_solar_phase_shift(self) -> float:
        """Calculates solar perturbation parameter eta * ||B||_2 * cos(w_c * t)."""
        b_norm = float(np.linalg.norm(self.magnetic_vector))
        return b_norm * np.cos(self.cycle_frequency * self.timestamp)


class SolarAugmentedQuantumKernel:
    """
    High-throughput 2-qubit Quantum Feature Map Kernel parameterized by solar inputs.
    Calculates Hilbert transition probabilities and encodes outputs into watermarked binary streams.
    """

    __slots__ = ("n_qubits", "dim", "watermark", "solar_input")

    def __init__(
        self,
        n_qubits: int = 2,
        watermark: bytes = b"CRA_PROTOCOL_v2.1",
        solar_input: Optional[SolarVectorInput] = None,
    ):
        self.n_qubits = n_qubits
        self.dim = 2 ** n_qubits
        self.watermark = watermark
        self.solar_input = solar_input if solar_input is not None else SolarVectorInput()

    def _get_rx(self, theta: float) -> np.ndarray:
        half = theta / 2.0
        return np.array([
            [np.cos(half), -1j * np.sin(half)],
            [-1j * np.sin(half), np.cos(half)]
        ], dtype=complex)

    def _get_rz(self, theta: float) -> np.ndarray:
        half = theta / 2.0
        return np.array([
            [np.exp(-1j * half), 0.0],
            [0.0, np.exp(1j * half)]
        ], dtype=complex)

    def _get_cz(self) -> np.ndarray:
        return np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, -1.0]
        ], dtype=complex)

    def modulate_features(self, x: np.ndarray) -> np.ndarray:
        """Applies solar flux and magnetic vector field scaling to input feature vector x."""
        solar = self.solar_input
        gamma = 0.1
        eta = 10.0

        flux_scale = 1.0 + gamma * np.log10(max(solar.flux_density, 1e-6))
        phase_shift = eta * solar.compute_solar_phase_shift()

        return x * flux_scale + phase_shift

    def feature_map(self, x: np.ndarray) -> np.ndarray:
        """Constructs solar-augmented unitary transformation U(x, S)."""
        if len(x) != 2:
            raise ValueError("Input feature vector x must be 2-dimensional.")

        x_mod = self.modulate_features(x)

        H = (1.0 / np.sqrt(2.0)) * np.array([[1.0, 1.0], [1.0, -1.0]], dtype=complex)
        H2 = np.kron(H, H)

        rx1, rx2 = self._get_rx(x_mod[0]), self._get_rx(x_mod[1])
        rz1, rz2 = self._get_rz(x_mod[0] * x_mod[1]), self._get_rz(x_mod[0] * x_mod[1])

        rot_stage1 = np.kron(rx1, rx2)
        rot_stage2 = np.kron(rz1, rz2)
        cz = self._get_cz()

        return cz @ rot_stage2 @ rot_stage1 @ H2

    def compute_fidelity(self, x1: np.ndarray, x2: np.ndarray) -> float:
        """Computes transition fidelity K(x1, x2; S) = |<00| U_dag(x1, S) U(x2, S) |00>|^2."""
        psi_0 = np.zeros(self.dim, dtype=complex)
        psi_0[0] = 1.0

        U_x1 = self.feature_map(x1)
        U_x2 = self.feature_map(x2)

        state1 = U_x1 @ psi_0
        state2 = U_x2 @ psi_0

        overlap = np.vdot(state1, state2)
        return float(np.abs(overlap) ** 2)

    def evaluate_gram_matrix(self, X: np.ndarray) -> np.ndarray:
        """Computes symmetric Gram matrix for dataset X using solar quantum kernels."""
        N = len(X)
        gram = np.zeros((N, N), dtype=float)

        for i in range(N):
            gram[i, i] = 1.0
            for j in range(i + 1, N):
                val = self.compute_fidelity(X[i], X[j])
                gram[i, j] = val
                gram[j, i] = val

        return gram

    def export_gram_matrix_bytes(self, X: np.ndarray) -> bytes:
        """Exports Gram matrix into a watermarked Little-Endian byte stream with instrument keys."""
        gram = self.evaluate_gram_matrix(X)
        writer = WatermarkedLittleEndianWriter(watermark=self.watermark)

        rows, cols = gram.shape
        writer._buffer.extend((rows & 0xFFFFFFFF).to_bytes(4, byteorder="little"))
        writer._buffer.extend((cols & 0xFFFFFFFF).to_bytes(4, byteorder="little"))

        for val in gram.flat:
            writer.write_f64(val)

        return writer.to_bytes()


if __name__ == "__main__":
    # Define solar environmental parameters
    solar_env = SolarVectorInput(
        flux_density=1361.5,
        magnetic_vector=(1.2e-4, -5.0e-5, 3.1e-4),
        cycle_frequency=2.86e-6,
        timestamp=86400.0,
    )

    kernel = SolarAugmentedQuantumKernel(n_qubits=2, solar_input=solar_env)

    x_a = np.array([0.45, 1.20])
    x_b = np.array([0.45, 1.20])
    x_c = np.array([2.10, -0.85])

    print("K(a, b) [Solar Modulated - Identical] :", kernel.compute_fidelity(x_a, x_b))
    print("K(a, c) [Solar Modulated - Distinct]  :", kernel.compute_fidelity(x_a, x_c))

    # Binary stream serialization and verification check
    dataset = np.array([x_a, x_c])
    stream_bytes = kernel.export_gram_matrix_bytes(dataset)

    reader = WatermarkedLittleEndianReader(stream_bytes, expected_watermark=b"CRA_PROTOCOL_v2.1")
    print("Stream Watermark Validated:", reader.watermark.decode("utf-8"))
    print("Piano Key Hex             :", hex(reader.piano_key))
    print("Violin Key Hex            :", hex(reader.violin_key))
