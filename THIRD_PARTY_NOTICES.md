# Avisos de terceros

La licencia [AGPL-3.0-only](LICENSE) cubre solo el código de PharmaSignal. Los
paquetes y los datos de terceros conservan sus propias condiciones, que se recogen
aquí.

Fichero generado con `python scripts/deps/generar_avisos.py`: no se edita a mano.
Las licencias son las que declara cada paquete en sus metadatos.

## Paquetes de Python

Incluye `requirements.txt` (44 paquetes) y `requirements-interfaz.txt` (39
paquetes, con las mismas versiones). Todas las licencias de esta tabla son
compatibles con la AGPL-3.0.

| Paquete | Versión | Licencia declarada | En la imagen Docker |
| --- | --- | --- | --- |
| altair | 6.2.2 | BSD License | Sí |
| anyio | 4.14.2 | MIT | Sí |
| arro3-core | 0.8.1 | MIT OR Apache-2.0 | Sí |
| attrs | 26.1.0 | MIT | Sí |
| certifi | 2026.10.18 | Mozilla Public License 2.0 (MPL 2.0) | Sí |
| charset-normalizer | 3.4.9 | MIT | Sí |
| click | 8.4.2 | BSD-3-Clause | Sí |
| delta-spark | 4.3.1 | Apache Software License | No |
| deltalake | 1.6.2 | Apache-2.0 | Sí |
| deprecated | 1.3.1 | MIT License | Sí |
| h11 | 0.16.0 | MIT License | Sí |
| idna | 3.18 | BSD-3-Clause | Sí |
| importlib-metadata | 8.7.1 | Apache-2.0 | No |
| itsdangerous | 2.2.0 | BSD License | Sí |
| jinja2 | 3.1.6 | BSD License | Sí |
| jsonschema | 4.26.0 | MIT | Sí |
| jsonschema-specifications | 2025.9.1 | MIT | Sí |
| markupsafe | 3.0.3 | BSD-3-Clause | Sí |
| narwhals | 2.23.0 | MIT | Sí |
| numpy | 2.5.1 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Sí |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | Sí |
| pandas | 3.0.3 | BSD License | Sí |
| pillow | 13.0.0 | MIT-CMU | Sí |
| plotly | 6.9.0 | MIT | Sí |
| protobuf | 7.35.1 | 3-Clause BSD License | Sí |
| py4j | 0.10.9.9 | BSD License | No |
| pyarrow | 24.0.0 | Apache-2.0 | Sí |
| pydeck | 0.9.3 | Apache License 2.0 | Sí |
| pyspark | 4.1.1 | Apache-2.0 | No |
| python-dateutil | 2.9.0.post0 | BSD License / Apache Software License | Sí |
| python-multipart | 0.0.32 | Apache-2.0 | Sí |
| referencing | 0.37.0 | MIT | Sí |
| requests | 2.34.2 | Apache Software License | Sí |
| rpds-py | 2026.6.3 | MIT | Sí |
| six | 1.17.0 | MIT License | Sí |
| starlette | 1.3.1 | BSD-3-Clause | Sí |
| streamlit | 1.66.1 | Apache-2.0 | Sí |
| typing-extensions | 4.16.0 | PSF-2.0 | Sí |
| urllib3 | 2.8.0 | MIT | Sí |
| uvicorn | 0.51.0 | BSD-3-Clause | Sí |
| watchdog | 6.0.0 | Apache Software License | Sí |
| websockets | 16.0 | BSD-3-Clause | Sí |
| wrapt | 2.2.2 | BSD-2-Clause | Sí |
| zipp | 4.1.0 | MIT | No |

## Entorno opcional de traducción

`requirements-traduccion.txt` (89 paquetes) es el venv aparte de
`src/curacion/traducir_terminos.py`. Este entorno no se distribuye: no va ni en la
imagen Docker ni en el repositorio.

| Paquete | Versión | Licencia declarada |
| --- | --- | --- |
| annotated-doc | 0.0.4 | MIT |
| annotated-types | 0.7.0 | MIT License |
| anyio | 4.14.2 | MIT |
| argostranslate | 1.11.0 | MIT License |
| arro3-core | 0.8.1 | MIT OR Apache-2.0 |
| blis | 1.3.3 | BSD License |
| catalogue | 2.0.10 | MIT License |
| certifi | 2026.10.18 | Mozilla Public License 2.0 (MPL 2.0) |
| charset-normalizer | 3.4.9 | MIT |
| click | 8.4.2 | BSD-3-Clause |
| cloudpathlib | 0.24.0 | MIT License |
| confection | 1.3.3 | MIT License |
| ctranslate2 | 4.8.1 | MIT |
| cuda-pathfinder | 1.5.6 | Apache-2.0 |
| cymem | 2.0.13 | MIT License |
| deltalake | 1.6.2 | Apache-2.0 |
| deprecated | 1.3.1 | MIT License |
| emoji | 2.15.0 | BSD License |
| filelock | 4.2.1 | MIT |
| flatbuffers | 25.12.19 | Apache Software License |
| fsspec | 2026.6.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD License |
| idna | 3.18 | BSD-3-Clause |
| jinja2 | 3.1.6 | BSD License |
| joblib | 1.5.3 | BSD-3-Clause |
| markdown-it-py | 4.2.0 | MIT License |
| markupsafe | 3.0.3 | BSD-3-Clause |
| mdurl | 0.1.2 | MIT License |
| minisbd | 0.9.5 | GNU Affero General Public License v3 |
| mpmath | 1.3.0 | BSD License |
| murmurhash | 1.0.15 | MIT License |
| networkx | 3.6.1 | BSD-3-Clause |
| numpy | 2.5.1 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| onnxruntime | 1.27.0 | MIT License |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| pandas | 3.0.3 | BSD License |
| preshed | 3.0.13 | MIT License |
| protobuf | 7.35.1 | 3-Clause BSD License |
| pyarrow | 24.0.0 | Apache-2.0 |
| pydantic | 2.13.4 | MIT |
| pydantic-core | 2.46.4 | MIT |
| pygments | 2.20.0 | BSD-2-Clause |
| python-dateutil | 2.9.0.post0 | BSD License / Apache Software License |
| pyyaml | 6.0.3 | MIT License |
| regex | 2026.7.10 | Apache-2.0 AND CNRI-Python |
| requests | 2.34.2 | Apache Software License |
| rich | 15.0.0 | MIT License |
| sacremoses | 0.1.1 | MIT License |
| sentencepiece | 0.2.2 | Apache-2.0 |
| setuptools | 84.1.0 | MIT |
| shellingham | 1.5.4 | ISC License (ISCL) |
| six | 1.17.0 | MIT License |
| smart-open | 8.0.1 | MIT License |
| spacy | 3.8.14 | MIT License |
| spacy-legacy | 3.0.12 | MIT License |
| spacy-loggers | 1.0.5 | MIT |
| srsly | 2.5.3 | MIT License |
| stanza | 1.10.1 | Apache License 2.0 |
| sympy | 1.14.0 | BSD License |
| thinc | 8.3.13 | MIT License |
| torch | 2.13.0 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| tqdm | 4.68.4 | MPL-2.0 AND MIT |
| triton | 3.7.1 | MIT License |
| typer | 0.27.0 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.2 | MIT |
| urllib3 | 2.8.0 | MIT |
| wasabi | 1.1.3 | MIT |
| weasel | 1.0.0 | MIT License |
| wrapt | 2.2.2 | BSD-2-Clause |

### Bibliotecas CUDA de NVIDIA

`torch` arrastra las bibliotecas CUDA de NVIDIA, con licencia propietaria de NVIDIA.
Solo son dependencias de este entorno opcional y tampoco se distribuyen.

| Paquete | Versión | Licencia declarada |
| --- | --- | --- |
| cuda-bindings | 13.3.1 | LicenseRef-NVIDIA-SOFTWARE-LICENSE |
| cuda-toolkit | 13.0.3.0 | no declarada en los metadatos |
| nvidia-cublas | 13.1.1.3 | LicenseRef-NVIDIA-Proprietary |
| nvidia-cuda-cupti | 13.0.85 | Other/Proprietary License |
| nvidia-cuda-nvrtc | 13.0.88 | Other/Proprietary License |
| nvidia-cuda-runtime | 13.0.96 | LicenseRef-NVIDIA-Proprietary |
| nvidia-cudnn-cu13 | 9.20.0.48 | LicenseRef-NVIDIA-Proprietary |
| nvidia-cufft | 12.0.0.61 | Other/Proprietary License |
| nvidia-cufile | 1.15.1.6 | Other/Proprietary License |
| nvidia-curand | 10.4.0.35 | Other/Proprietary License |
| nvidia-cusolver | 12.0.4.66 | Other/Proprietary License |
| nvidia-cusparse | 12.6.3.3 | Other/Proprietary License |
| nvidia-cusparselt-cu13 | 0.8.1 | NVIDIA Proprietary Software |
| nvidia-nccl-cu13 | 2.29.7 | LicenseRef-NVIDIA-Proprietary |
| nvidia-nvjitlink | 13.3.33 | LicenseRef-NVIDIA-Proprietary |
| nvidia-nvshmem-cu13 | 3.4.5 | LicenseRef-NVIDIA-Proprietary |
| nvidia-nvtx | 13.0.85 | Other/Proprietary License |

## Datos

### FAERS y openFDA

Según los [términos de openFDA](https://open.fda.gov/terms/), su contenido es de
dominio público y se ofrece con la dedicación Creative Commons CC0 1.0 Universal,
salvo los datos marcados expresamente como no públicos. Se ofrece «tal cual», sin
garantías de ningún tipo: la FDA no garantiza que los datos estén libres de errores.

Una señal estadística es una hipótesis de trabajo, no una prueba de causalidad, y una
tasa de notificación no es una incidencia.

### MedDRA

MedDRA® es una marca registrada de la ICH. Los términos de reacción se usan tal como
vienen en FAERS. Este aviso no concede ningún derecho sobre MedDRA.

### Traducción de los términos

La traducción al español de los términos es automática, hecha con Argos Translate,
con un diccionario propio de correcciones (`data/diccionarios/terminos_es.txt`). No
es la traducción oficial de MedDRA al español.
