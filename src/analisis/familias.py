"""
familias.py
Definiciones de las familias de fármacos usadas en los análisis.

Fuente única: los módulos geográfico, temporal y de anomalías importan de aquí,
de modo que un cambio en una lista se propaga a todos. Antes cada módulo tenía
su propia copia de la lista de GLP-1, lo que es una fuente segura de descuadres
en cuanto una de las dos se toca y la otra no.

Nota sobre las grafías: los ficheros de la FDA contienen un artefacto de
exportación por el que un separador aparece como '?' en cuatro trimestres de
2020-2021 (2020q3, 2021q1, 2021q2 y 2021q3). Se ha decidido no corregirlo en la
curación, así que las listas incluyen ambas formas cuando el fármaco está
afectado.
"""

# GLP-1.
# Se incluyen principios activos y nombres comerciales porque la normalización
# de drugname no unifica marca y principio activo: en FAERS conviven las dos.
# Tirzepatida es agonista dual GIP/GLP-1, no un GLP-1 puro. Se incluye siguiendo
# la práctica habitual en la literatura de farmacovigilancia, y se declara
# explícitamente en la memoria.
# Respecto a la versión de E2 se añaden byetta, bydureon, bydureon bcise,
# lixisenatide, lyxumia y adlyxin: son marcas de principios activos que ya
# estaban en la lista pero cuyos nombres comerciales faltaban, de modo que se
# perdían unos 10.900 reportes.
GLP1 = [
    "semaglutide", "ozempic", "wegovy", "rybelsus",
    "tirzepatide", "mounjaro", "zepbound",
    "liraglutide", "saxenda", "victoza",
    "dulaglutide", "trulicity",
    "exenatide", "byetta", "bydureon", "bydureon bcise",
    "lixisenatide", "lyxumia", "adlyxin",
]

# Excluidos de GLP1 a propósito. Se documenta en la memoria.
# - soliqua y xultophy: combinaciones fijas con insulina. En un análisis sobre
#   sospechoso primario no puede atribuirse el evento al componente GLP-1.
# - semaglutida y tirzepatida compuestas con vitaminas: formulación magistral,
#   no producto autorizado. La FDA emitió alertas específicas en 2023-2024.
GLP1_EXCLUIDOS = [
    "soliqua 100/33", "xultophy 100/3.6",
    "cyanocobalamin\\semaglutide", "cyanocobalamin\\tirzepatide",
    "cyanocobalamin\\glycine\\semaglutide", "cyanocobalamin\\glycine\\tirzepatide",
]

# Serie A. Antivirales específicos de COVID-19.
# Ninguno de estos fármacos tiene uso fuera de COVID, así que la serie es limpia.
# Se añaden los monoclonales, que faltaban en E2 (unas 17.500 filas).
COVID_ANTIVIRAL = [
    "paxlovid", "nirmatrelvir", "nirmatrelvir\\ritonavir",
    "remdesivir", "veklury", "molnupiravir", "lagevrio",
    "sotrovimab", "bebtelovimab", "bamlanivimab", "etesevimab",
    "bamlanivimab\\etesevimab", "bamlanivimab/etesevimab",
    "casirivimab", "imdevimab",
    "casirivimab\\imdevimab", "casirivimab/imdevimab",
    "casirivimab?imdevimab", "casirivimab and imdevimab",
    "regen-cov", "regen?cov",
    "tixagevimab", "cilgavimab", "cilgavimab\\tixagevimab", "evusheld",
]

# Serie B. Fármacos reutilizados durante la pandemia.
# NO son fármacos COVID: hidroxicloroquina y cloroquina son antipalúdicos cuya
# indicación principal es lupus y artritis reumatoide, y mantienen un volumen
# basal constante a lo largo de los 24 trimestres.
# Se separan de la serie A porque su pico de notificación (2020q4) y el de los
# antivirales (2022q3) están separados por dos años. Sumarlas produce una serie
# bimodal que no corresponde a ningún fenómeno real, y esa serie es justamente
# la entrada del detector de anomalías.
COVID_REPURPOSED = [
    "hydroxychloroquine", "chloroquine", "plaquenil", "aralen",
]

# Vacunas COVID-19. USO EXCLUSIVAMENTE DESCRIPTIVO.
# La notificación primaria de vacunas en Estados Unidos corresponde a VAERS, no
# a FAERS. Los 491 reportes que aparecen aquí como sospechoso primario llegaron
# por vías colaterales (notificación de fabricante, casos internacionales) y no
# constituyen una muestra representativa: son el 0,0056% de la base analítica.
# NO se calculan PRR ni ROR sobre esta familia, el denominador es arbitrario.
VACUNAS_COVID = [
    "comirnaty", "comirnaty nos",
    "covid-19 vaccine", "covid-19 vaccine nos",
    "covid?19 vaccine", "covid?19 vaccine nos",
    "pfizer-biontech covid-19 vaccine", "pfizer?biontech covid?19 vaccine",
    "pfizer-biontech covid-19 vaccine, bivalent",
    "moderna covid-19 vaccine", "moderna covid?19 vaccine", "spikevax",
    "astrazeneca covid-19 vaccine", "astrazeneca covid?19 vaccine", "vaxzevria",
    "janssen covid-19 vaccine", "janssen covid?19 vaccine", "jcovden",
    "nuvaxovid",
]

# Antivirales específicos de gripe.
# Se excluyen a propósito amantadina y rimantadina: aunque históricamente se
# usaron como antigripales, su indicación principal hoy es la enfermedad de
# Parkinson, así que meterlas contaminaría la serie igual que hacía la
# hidroxicloroquina con la de COVID.
GRIPE_ANTIVIRAL = [
    "tamiflu", "oseltamivir", "oseltamivir phosphate",
    "xofluza", "baloxavir marboxil",
    "relenza", "zanamivir",
    "rapivab", "peramivir",
]

# Anticuerpos monoclonales frente al virus respiratorio sincitial (VRS).
# Interesa por dos motivos: palivizumab (Synagis) lleva autorizado desde 1998 y
# da una serie estable, mientras que nirsevimab (Beyfortus) se autorizó en 2023,
# de modo que aparece desde cero a mitad del periodo analizado. Es un caso de
# anomalía con fecha externa verificable.
VSR_MONOCLONAL = [
    "synagis", "palivizumab",
    "beyfortus", "nirsevimab", "nirsevimab-alip",
]

# Familias sobre las que SÍ se calculan señales y series temporales
FAMILIAS = {
    "glp1": GLP1,
    "covid_antiviral": COVID_ANTIVIRAL,
    "covid_repurposed": COVID_REPURPOSED,
    "gripe_antiviral": GRIPE_ANTIVIRAL,
    "vsr_monoclonal": VSR_MONOCLONAL,
}

# Familias descriptivas, fuera del cálculo de señales
FAMILIAS_DESCRIPTIVAS = {
    "vacunas_covid": VACUNAS_COVID,
}