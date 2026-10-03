"""Centralized configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()

_USER = os.getenv("POSTGRES_USER", "postgres")
_PASS = os.getenv("POSTGRES_PASSWORD", "secret")
_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
_PORT = os.getenv("POSTGRES_PORT", "5432")
_DB = os.getenv("POSTGRES_DB", "newsrag")
POSTGRES_URL = f"postgresql://{_USER}:{_PASS}@{_HOST}:{_PORT}/{_DB}"
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6335")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
GOOGLE_DRIVE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH", "credentials.json")

# Scraping — RSS search queries grouped by topic category and sub_area, and
# RSS/HTML fetch settings (feedparser + googlenewsdecoder + trafilatura).
# TOPIC_QUERIES: dict[str, dict[str, list[dict]]] = {
#     "general_mental_health": {
#         "General Overview": [
#             {"keyword": "teen mental health Indonesia"},
#             {"keyword": "student mental health Indonesia"},
#             {"keyword": "youth mental health Indonesia"},
#             {"keyword": "adolescent mental health Indonesia"},
#         ],
#         "Mental Disorders": [
#             {"keyword": "teen mental disorders Indonesia"},
#             {"keyword": "student mental disorders Indonesia"},
#             {"keyword": "adolescent anxiety disorder Indonesia"},
#             {"keyword": "teen depression disorder Indonesia"},
#             {"keyword": "youth bipolar disorder Indonesia"},
#             {"keyword": "teen ADHD Indonesia"},
#         ],
#         "Awareness & Literacy": [
#             {"keyword": "teen mental health awareness Indonesia"},
#             {"keyword": "youth mental health stigma Indonesia"},
#             {"keyword": "adolescent mental health literacy Indonesia"},
#             {"keyword": "student mental health education Indonesia"},
#             {"keyword": "youth mental health campaign Indonesia"},
#         ],
#     },
#     "self_harm_suicide": {
#         "Self-Harm": [
#             {"keyword": "teen self-harm Indonesia"},
#             {"keyword": "student self-harm Indonesia"},
#             {"keyword": "youth self-harm Indonesia"},
#             {"keyword": "adolescent self-injury Indonesia"},
#             {"keyword": "teen cutting behavior Indonesia"},
#         ],
#         "Suicide": [
#             {"keyword": "teen suicide Indonesia"},
#             {"keyword": "student suicide Indonesia"},
#             {"keyword": "youth suicide prevention Indonesia"},
#             {"keyword": "adolescent suicidal ideation Indonesia"},
#             {"keyword": "teen suicide attempt Indonesia"},
#             {"keyword": "student suicidal thoughts Indonesia"},
#             {"keyword": "youth suicide hotline Indonesia"},
#         ],
#         "Crisis Support": [
#             {"keyword": "teen mental health crisis Indonesia"},
#             {"keyword": "youth crisis intervention Indonesia"},
#             {"keyword": "adolescent emergency mental health Indonesia"},
#         ],
#     },
#     "academic_social_stressors": {
#         "Academic Pressure": [
#             {"keyword": "teen academic stress Indonesia"},
#             {"keyword": "student academic stress Indonesia"},
#             {"keyword": "youth exam pressure Indonesia"},
#             {"keyword": "adolescent school burnout Indonesia"},
#             {"keyword": "student exam anxiety Indonesia"},
#         ],
#         "Social Media": [
#             {"keyword": "teen social media pressure Indonesia"},
#             {"keyword": "student social media pressure Indonesia"},
#             {"keyword": "youth social media addiction Indonesia"},
#             {"keyword": "adolescent Instagram anxiety Indonesia"},
#             {"keyword": "teen TikTok mental health Indonesia"},
#         ],
#         "Online Harassment": [
#             {"keyword": "teen cyberbullying Indonesia"},
#             {"keyword": "student cyberbullying Indonesia"},
#             {"keyword": "youth online harassment Indonesia"},
#             {"keyword": "adolescent digital abuse Indonesia"},
#             {"keyword": "student online bullying mental health Indonesia"},
#         ],
#     },
#     "family_domestic_environment": {
#         "Parenting Dynamics": [
#             {"keyword": "toxic parenting and teen mental health Indonesia"},
#             {"keyword": "toxic parenting and student mental health Indonesia"},
#             {"keyword": "parenting styles and teens Indonesia"},
#             {"keyword": "parenting styles and students Indonesia"},
#             {"keyword": "helicopter parenting teen anxiety Indonesia"},
#             {"keyword": "authoritarian parenting teen depression Indonesia"},
#         ],
#         "Domestic Conflict & Separation": [
#             {"keyword": "domestic violence impact on teens Indonesia"},
#             {"keyword": "domestic violence impact on students Indonesia"},
#             {"keyword": "parental divorce impact on teens Indonesia"},
#             {"keyword": "parental divorce impact on students Indonesia"},
#             {"keyword": "family conflict teen mental health Indonesia"},
#             {"keyword": "single parent teen mental health Indonesia"},
#         ],
#         "Economic Stress": [
#             {"keyword": "family poverty teen mental health Indonesia"},
#             {"keyword": "economic hardship adolescent depression Indonesia"},
#             {"keyword": "low income family teen mental health Indonesia"},
#         ],
#     },
#     "data_surveys_statistics": {
#         "General Surveys": [
#             {"keyword": "teen mental health survey Indonesia"},
#             {"keyword": "student mental health survey Indonesia"},
#             {"keyword": "youth mental health prevalence Indonesia"},
#             {"keyword": "adolescent mental health statistics Indonesia"},
#             {"keyword": "youth mental health report Indonesia"},
#         ],
#         "Suicide Metrics": [
#             {"keyword": "teen suicide data Indonesia"},
#             {"keyword": "student suicide data Indonesia"},
#             {"keyword": "youth suicide rate Indonesia"},
#             {"keyword": "adolescent suicide statistics Indonesia"},
#             {"keyword": "teen suicide trend Indonesia"},
#         ],
#         "Depression & Anxiety Metrics": [
#             {"keyword": "teen depression statistics Indonesia"},
#             {"keyword": "student depression statistics Indonesia"},
#             {"keyword": "youth depression prevalence Indonesia"},
#             {"keyword": "adolescent anxiety statistics Indonesia"},
#             {"keyword": "teen mental illness rate Indonesia"},
#         ],
#     },
#     "substance_use": {
#         "Substance Use": [
#             {"keyword": "teen drug use Indonesia"},
#             {"keyword": "student drug abuse Indonesia"},
#             {"keyword": "youth substance abuse Indonesia"},
#             {"keyword": "adolescent alcohol use Indonesia"},
#             {"keyword": "teen inhalant abuse Indonesia"},
#         ],
#         "Addiction": [
#             {"keyword": "teen smoking mental health Indonesia"},
#             {"keyword": "student vaping mental health Indonesia"},
#             {"keyword": "youth drug addiction Indonesia"},
#             {"keyword": "adolescent addiction treatment Indonesia"},
#             {"keyword": "teen methamphetamine Indonesia"},
#         ],
#         "Prevention": [
#             {"keyword": "teen substance abuse prevention Indonesia"},
#             {"keyword": "student drug prevention program Indonesia"},
#             {"keyword": "youth rehabilitation center Indonesia"},
#             {"keyword": "adolescent drug education Indonesia"},
#             {"keyword": "teen narcotics awareness Indonesia"},
#         ],
#     },
#     "digital_wellbeing": {
#         "Screen Time & Gaming": [
#             {"keyword": "teen screen time mental health Indonesia"},
#             {"keyword": "student smartphone addiction Indonesia"},
#             {"keyword": "youth internet addiction Indonesia"},
#             {"keyword": "adolescent gaming disorder Indonesia"},
#             {"keyword": "teen online gaming mental health Indonesia"},
#         ],
#         "Social Media Addiction": [
#             {"keyword": "teen social media addiction Indonesia"},
#             {"keyword": "student Instagram depression Indonesia"},
#             {"keyword": "youth TikTok anxiety Indonesia"},
#             {"keyword": "adolescent social media detox Indonesia"},
#             {"keyword": "teen Facebook mental health Indonesia"},
#         ],
#         "Digital Wellbeing": [
#             {"keyword": "teen digital wellbeing Indonesia"},
#             {"keyword": "student phone addiction mental health Indonesia"},
#             {"keyword": "adolescent digital literacy mental health Indonesia"},
#             {"keyword": "youth screen time regulation Indonesia"},
#             {"keyword": "teen digital detox mental health Indonesia"},
#         ],
#     },
#     "peer_and_school_environment": {
#         "Bullying": [
#             {"keyword": "teen school bullying Indonesia"},
#             {"keyword": "student bullying mental health Indonesia"},
#             {"keyword": "youth peer bullying Indonesia"},
#             {"keyword": "adolescent bullying depression Indonesia"},
#         ],
#         "Social Isolation": [
#             {"keyword": "teen loneliness Indonesia"},
#             {"keyword": "student social isolation mental health Indonesia"},
#             {"keyword": "youth peer rejection Indonesia"},
#             {"keyword": "adolescent friendship problems mental health Indonesia"},
#         ],
#         "School Climate": [
#             {"keyword": "teen school environment mental health Indonesia"},
#             {"keyword": "student teacher relationship mental health Indonesia"},
#             {"keyword": "youth school dropout mental health Indonesia"},
#             {"keyword": "adolescent school refusal Indonesia"},
#         ],
#         "Peer Pressure": [
#             {"keyword": "teen peer pressure Indonesia"},
#             {"keyword": "student peer influence mental health Indonesia"},
#             {"keyword": "adolescent conformity peer pressure Indonesia"},
#         ],
#     },
#     "mental_health_support": {
#         "Help Seeking": [
#             {"keyword": "teen therapy Indonesia"},
#             {"keyword": "student counseling Indonesia"},
#             {"keyword": "youth mental health services Indonesia"},
#             {"keyword": "adolescent psychiatric care Indonesia"},
#         ],
#         "Barriers": [
#             {"keyword": "teen mental health stigma Indonesia"},
#             {"keyword": "student help seeking behavior Indonesia"},
#             {"keyword": "youth counseling access Indonesia"},
#             {"keyword": "adolescent mental health treatment barriers Indonesia"},
#         ],
#         "School & Community Support": [
#             {"keyword": "teen school counselor Indonesia"},
#             {"keyword": "student mental health program Indonesia"},
#             {"keyword": "youth peer support mental health Indonesia"},
#             {"keyword": "adolescent mental health intervention Indonesia"},
#         ],
#         "Policy & Resources": [
#             {"keyword": "teen mental health policy Indonesia"},
#             {"keyword": "youth mental health awareness program Indonesia"},
#             {"keyword": "student mental health funding Indonesia"},
#         ],
#     },
#     "trauma_and_resilience": {
#         "Trauma": [
#             {"keyword": "teen childhood trauma Indonesia"},
#             {"keyword": "student trauma mental health Indonesia"},
#             {"keyword": "youth PTSD Indonesia"},
#             {"keyword": "adolescent abuse trauma Indonesia"},
#             {"keyword": "teen sexual abuse mental health Indonesia"},
#         ],
#         "Violence & Abuse": [
#             {"keyword": "teen domestic abuse Indonesia"},
#             {"keyword": "student violence trauma Indonesia"},
#             {"keyword": "youth neglect mental health Indonesia"},
#             {"keyword": "adolescent emotional abuse Indonesia"},
#         ],
#         "Resilience & Recovery": [
#             {"keyword": "teen resilience mental health Indonesia"},
#             {"keyword": "student coping skills mental health Indonesia"},
#             {"keyword": "youth resilience program Indonesia"},
#             {"keyword": "adolescent post-traumatic growth Indonesia"},
#             {"keyword": "teen mental health recovery Indonesia"},
#             {"keyword": "student mental health rehabilitation Indonesia"},
#         ],
#     },
# }

# TOPIC_QUERIES_ID: dict[str, dict[str, list[dict]]] = {
#     "general_mental_health": {
#         "General Overview": [
#             {"keyword": "kesehatan mental remaja Indonesia"},
#             {"keyword": "kesehatan mental pelajar Indonesia"},
#             {"keyword": "kesehatan mental anak muda Indonesia"},
#             {"keyword": "kesehatan mental remaja belia Indonesia"},
#         ],
#         "Mental Disorders": [
#             {"keyword": "gangguan mental remaja Indonesia"},
#             {"keyword": "gangguan mental pelajar Indonesia"},
#             {"keyword": "gangguan kecemasan remaja belia Indonesia"},
#             {"keyword": "gangguan depresi remaja Indonesia"},
#             {"keyword": "gangguan bipolar anak muda Indonesia"},
#             {"keyword": "ADHD remaja Indonesia"},
#         ],
#         "Awareness & Literacy": [
#             {"keyword": "kesadaran kesehatan mental remaja Indonesia"},
#             {"keyword": "stigma kesehatan mental anak muda Indonesia"},
#             {"keyword": "literasi kesehatan mental remaja belia Indonesia"},
#             {"keyword": "edukasi kesehatan mental pelajar Indonesia"},
#             {"keyword": "kampanye kesehatan mental anak muda Indonesia"},
#         ],
#     },
#     "self_harm_suicide": {
#         "Self-Harm": [
#             {"keyword": "melukai diri remaja Indonesia"},
#             {"keyword": "melukai diri pelajar Indonesia"},
#             {"keyword": "melukai diri anak muda Indonesia"},
#             {"keyword": "menyakiti diri remaja belia Indonesia"},
#             {"keyword": "perilaku menyayat diri remaja Indonesia"},
#         ],
#         "Suicide": [
#             {"keyword": "bunuh diri remaja Indonesia"},
#             {"keyword": "bunuh diri pelajar Indonesia"},
#             {"keyword": "pencegahan bunuh diri anak muda Indonesia"},
#             {"keyword": "ide bunuh diri remaja belia Indonesia"},
#             {"keyword": "percobaan bunuh diri remaja Indonesia"},
#             {"keyword": "pikiran bunuh diri pelajar Indonesia"},
#             {"keyword": "hotline bunuh diri anak muda Indonesia"},
#         ],
#         "Crisis Support": [
#             {"keyword": "krisis kesehatan mental remaja Indonesia"},
#             {"keyword": "intervensi krisis anak muda Indonesia"},
#             {"keyword": "darurat kesehatan mental remaja belia Indonesia"},
#         ],
#     },
#     "academic_social_stressors": {
#         "Academic Pressure": [
#             {"keyword": "stres akademik remaja Indonesia"},
#             {"keyword": "stres akademik pelajar Indonesia"},
#             {"keyword": "tekanan ujian anak muda Indonesia"},
#             {"keyword": "burnout sekolah remaja belia Indonesia"},
#             {"keyword": "kecemasan ujian pelajar Indonesia"},
#         ],
#         "Social Media": [
#             {"keyword": "tekanan media sosial remaja Indonesia"},
#             {"keyword": "tekanan media sosial pelajar Indonesia"},
#             {"keyword": "kecanduan media sosial anak muda Indonesia"},
#             {"keyword": "kecemasan Instagram remaja belia Indonesia"},
#             {"keyword": "kesehatan mental TikTok remaja Indonesia"},
#         ],
#         "Online Harassment": [
#             {"keyword": "perundungan siber remaja Indonesia"},
#             {"keyword": "perundungan siber pelajar Indonesia"},
#             {"keyword": "pelecehan daring anak muda Indonesia"},
#             {"keyword": "kekerasan digital remaja belia Indonesia"},
#             {"keyword": "kesehatan mental perundungan daring pelajar Indonesia"},
#         ],
#     },
#     "family_domestic_environment": {
#         "Parenting Dynamics": [
#             {"keyword": "pola asuh toksik dan kesehatan mental remaja Indonesia"},
#             {"keyword": "pola asuh toksik dan kesehatan mental pelajar Indonesia"},
#             {"keyword": "gaya pengasuhan dan remaja Indonesia"},
#             {"keyword": "gaya pengasuhan dan pelajar Indonesia"},
#             {"keyword": "pengasuhan helikopter kecemasan remaja Indonesia"},
#             {"keyword": "pengasuhan otoriter depresi remaja Indonesia"},
#         ],
#         "Domestic Conflict & Separation": [
#             {"keyword": "dampak kekerasan dalam rumah tangga pada remaja Indonesia"},
#             {"keyword": "dampak kekerasan dalam rumah tangga pada pelajar Indonesia"},
#             {"keyword": "dampak perceraian orang tua pada remaja Indonesia"},
#             {"keyword": "dampak perceraian orang tua pada pelajar Indonesia"},
#             {"keyword": "konflik keluarga kesehatan mental remaja Indonesia"},
#             {"keyword": "orang tua tunggal kesehatan mental remaja Indonesia"},
#         ],
#         "Economic Stress": [
#             {"keyword": "kemiskinan keluarga kesehatan mental remaja Indonesia"},
#             {"keyword": "kesulitan ekonomi depresi remaja belia Indonesia"},
#             {"keyword": "keluarga berpenghasilan rendah kesehatan mental remaja Indonesia"},
#         ],
#     },
#     "data_surveys_statistics": {
#         "General Surveys": [
#             {"keyword": "survei kesehatan mental remaja Indonesia"},
#             {"keyword": "survei kesehatan mental pelajar Indonesia"},
#             {"keyword": "prevalensi kesehatan mental anak muda Indonesia"},
#             {"keyword": "statistik kesehatan mental remaja belia Indonesia"},
#             {"keyword": "laporan kesehatan mental anak muda Indonesia"},
#         ],
#         "Suicide Metrics": [
#             {"keyword": "data bunuh diri remaja Indonesia"},
#             {"keyword": "data bunuh diri pelajar Indonesia"},
#             {"keyword": "angka bunuh diri anak muda Indonesia"},
#             {"keyword": "statistik bunuh diri remaja belia Indonesia"},
#             {"keyword": "tren bunuh diri remaja Indonesia"},
#         ],
#         "Depression & Anxiety Metrics": [
#             {"keyword": "statistik depresi remaja Indonesia"},
#             {"keyword": "statistik depresi pelajar Indonesia"},
#             {"keyword": "prevalensi depresi anak muda Indonesia"},
#             {"keyword": "statistik kecemasan remaja belia Indonesia"},
#             {"keyword": "angka gangguan jiwa remaja Indonesia"},
#         ],
#     },
#     "substance_use": {
#         "Substance Use": [
#             {"keyword": "penggunaan narkoba remaja Indonesia"},
#             {"keyword": "penyalahgunaan narkoba pelajar Indonesia"},
#             {"keyword": "penyalahgunaan zat anak muda Indonesia"},
#             {"keyword": "konsumsi alkohol remaja belia Indonesia"},
#             {"keyword": "penyalahgunaan inhalan remaja Indonesia"},
#         ],
#         "Addiction": [
#             {"keyword": "kesehatan mental merokok remaja Indonesia"},
#             {"keyword": "kesehatan mental vape pelajar Indonesia"},
#             {"keyword": "kecanduan narkoba anak muda Indonesia"},
#             {"keyword": "pengobatan kecanduan remaja belia Indonesia"},
#             {"keyword": "sabu-sabu remaja Indonesia"},
#         ],
#         "Prevention": [
#             {"keyword": "pencegahan penyalahgunaan zat remaja Indonesia"},
#             {"keyword": "program pencegahan narkoba pelajar Indonesia"},
#             {"keyword": "pusat rehabilitasi anak muda Indonesia"},
#             {"keyword": "edukasi narkoba remaja belia Indonesia"},
#             {"keyword": "kesadaran narkotika remaja Indonesia"},
#         ],
#     },
#     "digital_wellbeing": {
#         "Screen Time & Gaming": [
#             {"keyword": "kesehatan mental waktu layar remaja Indonesia"},
#             {"keyword": "kecanduan smartphone pelajar Indonesia"},
#             {"keyword": "kecanduan internet anak muda Indonesia"},
#             {"keyword": "gangguan bermain gim remaja belia Indonesia"},
#             {"keyword": "kesehatan mental gim daring remaja Indonesia"},
#         ],
#         "Social Media Addiction": [
#             {"keyword": "kecanduan media sosial remaja Indonesia"},
#             {"keyword": "depresi Instagram pelajar Indonesia"},
#             {"keyword": "kecemasan TikTok anak muda Indonesia"},
#             {"keyword": "detoks media sosial remaja belia Indonesia"},
#             {"keyword": "kesehatan mental Facebook remaja Indonesia"},
#         ],
#         "Digital Wellbeing": [
#             {"keyword": "kesejahteraan digital remaja Indonesia"},
#             {"keyword": "kesehatan mental kecanduan ponsel pelajar Indonesia"},
#             {"keyword": "kesehatan mental literasi digital remaja belia Indonesia"},
#             {"keyword": "regulasi waktu layar anak muda Indonesia"},
#             {"keyword": "kesehatan mental detoks digital remaja Indonesia"},
#         ],
#     },
#     "peer_and_school_environment": {
#         "Bullying": [
#             {"keyword": "perundungan sekolah remaja Indonesia"},
#             {"keyword": "kesehatan mental perundungan pelajar Indonesia"},
#             {"keyword": "perundungan sebaya anak muda Indonesia"},
#             {"keyword": "depresi akibat perundungan remaja belia Indonesia"},
#         ],
#         "Social Isolation": [
#             {"keyword": "kesepian remaja Indonesia"},
#             {"keyword": "kesehatan mental isolasi sosial pelajar Indonesia"},
#             {"keyword": "penolakan sebaya anak muda Indonesia"},
#             {"keyword": "kesehatan mental masalah pertemanan remaja belia Indonesia"},
#         ],
#         "School Climate": [
#             {"keyword": "kesehatan mental lingkungan sekolah remaja Indonesia"},
#             {"keyword": "kesehatan mental hubungan guru murid pelajar Indonesia"},
#             {"keyword": "kesehatan mental putus sekolah anak muda Indonesia"},
#             {"keyword": "penolakan sekolah remaja belia Indonesia"},
#         ],
#         "Peer Pressure": [
#             {"keyword": "tekanan teman sebaya remaja Indonesia"},
#             {"keyword": "kesehatan mental pengaruh teman sebaya pelajar Indonesia"},
#             {"keyword": "konformitas tekanan teman sebaya remaja belia Indonesia"},
#         ],
#     },
#     "mental_health_support": {
#         "Help Seeking": [
#             {"keyword": "terapi remaja Indonesia"},
#             {"keyword": "konseling pelajar Indonesia"},
#             {"keyword": "layanan kesehatan mental anak muda Indonesia"},
#             {"keyword": "perawatan psikiatri remaja belia Indonesia"},
#         ],
#         "Barriers": [
#             {"keyword": "stigma kesehatan mental remaja Indonesia"},
#             {"keyword": "perilaku mencari bantuan pelajar Indonesia"},
#             {"keyword": "akses konseling anak muda Indonesia"},
#             {"keyword": "hambatan pengobatan kesehatan mental remaja belia Indonesia"},
#         ],
#         "School & Community Support": [
#             {"keyword": "konselor sekolah remaja Indonesia"},
#             {"keyword": "program kesehatan mental pelajar Indonesia"},
#             {"keyword": "dukungan sebaya kesehatan mental anak muda Indonesia"},
#             {"keyword": "intervensi kesehatan mental remaja belia Indonesia"},
#         ],
#         "Policy & Resources": [
#             {"keyword": "kebijakan kesehatan mental remaja Indonesia"},
#             {"keyword": "program kesadaran kesehatan mental anak muda Indonesia"},
#             {"keyword": "pendanaan kesehatan mental pelajar Indonesia"},
#         ],
#     },
#     "trauma_and_resilience": {
#         "Trauma": [
#             {"keyword": "trauma masa kecil remaja Indonesia"},
#             {"keyword": "kesehatan mental trauma pelajar Indonesia"},
#             {"keyword": "PTSD anak muda Indonesia"},
#             {"keyword": "trauma kekerasan remaja belia Indonesia"},
#             {"keyword": "kesehatan mental kekerasan seksual remaja Indonesia"},
#         ],
#         "Violence & Abuse": [
#             {"keyword": "kekerasan dalam rumah tangga remaja Indonesia"},
#             {"keyword": "trauma kekerasan pelajar Indonesia"},
#             {"keyword": "kesehatan mental penelantaran anak muda Indonesia"},
#             {"keyword": "kekerasan emosional remaja belia Indonesia"},
#         ],
#         "Resilience & Recovery": [
#             {"keyword": "kesehatan mental resiliensi remaja Indonesia"},
#             {"keyword": "kesehatan mental keterampilan koping pelajar Indonesia"},
#             {"keyword": "program resiliensi anak muda Indonesia"},
#             {"keyword": "pertumbuhan pasca-trauma remaja belia Indonesia"},
#             {"keyword": "pemulihan kesehatan mental remaja Indonesia"},
#             {"keyword": "rehabilitasi kesehatan mental pelajar Indonesia"},
#         ],
#     },
# }

# Active queries: refreshed keyword variations layered on top of the
# categories above, covering city-specific angles (Jakarta, Surabaya,
# Bandung, Yogyakarta, Medan), previously-uncovered conditions (eating
# disorder, OCD, panic attack, schizophrenia), underrepresented
# demographics (pesantren students, SMK/vocational students, orphan
# teens, children of migrant workers/TKI), interventions (mindfulness,
# art therapy, peer counseling, school mental health programs),
# post-pandemic mental health, natural disaster survivors, the
# pesantren/Islamic schooling angle, online learning anxiety, financial
# stress, and Gen Z mental health.
TOPIC_QUERIES: dict[str, dict[str, list[dict]]] = {
    "general_mental_health": {
        "Conditions": [
            {"keyword": "teen eating disorder Indonesia"},
            {"keyword": "student anorexia Indonesia"},
            {"keyword": "adolescent bulimia Indonesia"},
            {"keyword": "teen OCD Indonesia"},
            {"keyword": "student obsessive compulsive disorder Indonesia"},
            {"keyword": "teen panic attack Indonesia"},
            {"keyword": "adolescent panic disorder Indonesia"},
            {"keyword": "teen schizophrenia Indonesia"},
            {"keyword": "youth psychosis Indonesia"},
        ],
        "Gen Z & City": [
            {"keyword": "Gen Z mental health Indonesia"},
            {"keyword": "Gen Z mental health Jakarta"},
            {"keyword": "teen mental health Surabaya"},
            {"keyword": "teen mental health Bandung"},
            {"keyword": "teen mental health Yogyakarta"},
            {"keyword": "teen mental health Medan"},
        ],
    },
    "self_harm_suicide": {
        "City-Specific": [
            {"keyword": "teen suicide Jakarta"},
            {"keyword": "student suicide Surabaya"},
            {"keyword": "teen self-harm Bandung"},
            {"keyword": "student suicide Yogyakarta"},
            {"keyword": "teen suicide Medan"},
        ],
        "Disaster & Crisis": [
            {"keyword": "disaster survivor teen suicide risk Indonesia"},
            {"keyword": "earthquake survivor teen mental health crisis Indonesia"},
            {"keyword": "flood survivor teen self-harm Indonesia"},
            {"keyword": "tsunami survivor youth suicide Indonesia"},
        ],
        "Financial Stress": [
            {"keyword": "financial stress teen suicide Indonesia"},
            {"keyword": "economic pressure student suicide Indonesia"},
            {"keyword": "poverty related teen self-harm Indonesia"},
            {"keyword": "debt stress youth suicide Indonesia"},
            {"keyword": "unemployment stress teen suicide Indonesia"},
            {"keyword": "family financial crisis teen suicide Indonesia"},
        ],
    },
    "academic_social_stressors": {
        "Online Learning": [
            {"keyword": "online learning anxiety Indonesia"},
            {"keyword": "remote learning stress students Indonesia"},
            {"keyword": "e-learning burnout teens Indonesia"},
            {"keyword": "distance learning mental health Indonesia"},
            {"keyword": "Zoom fatigue students Indonesia"},
        ],
        "Vocational Students": [
            {"keyword": "SMK student mental health Indonesia"},
            {"keyword": "vocational school student stress Indonesia"},
            {"keyword": "vocational high school anxiety Indonesia"},
            {"keyword": "SMK student burnout Indonesia"},
        ],
        "Financial Stress": [
            {"keyword": "financial stress student Indonesia"},
            {"keyword": "tuition fee stress student Indonesia"},
            {"keyword": "scholarship pressure student Indonesia"},
            {"keyword": "part-time job stress student Indonesia"},
            {"keyword": "economic anxiety teen Indonesia"},
            {"keyword": "family income stress teen student Indonesia"},
        ],
    },
    "family_domestic_environment": {
        "Migrant Worker Families": [
            {"keyword": "children of migrant workers mental health Indonesia"},
            {"keyword": "TKI children mental health Indonesia"},
            {"keyword": "migrant worker family teen anxiety Indonesia"},
            {"keyword": "left-behind children mental health Indonesia"},
            {"keyword": "overseas worker family teen depression Indonesia"},
        ],
        "Orphan Teens": [
            {"keyword": "orphan teen mental health Indonesia"},
            {"keyword": "orphanage teen depression Indonesia"},
            {"keyword": "orphan adolescent trauma Indonesia"},
            {"keyword": "parentless teen mental health Indonesia"},
        ],
        "Financial Stress": [
            {"keyword": "family financial stress teen mental health Indonesia"},
            {"keyword": "household debt teen anxiety Indonesia"},
            {"keyword": "poverty stricken family teen depression Indonesia"},
            {"keyword": "economic hardship orphan teen Indonesia"},
            {"keyword": "low income family teen stress Indonesia"},
            {"keyword": "financial instability teen mental health Indonesia"},
        ],
    },
    "data_surveys_statistics": {
        "City-Specific Surveys": [
            {"keyword": "teen mental health survey Jakarta"},
            {"keyword": "student mental health data Surabaya"},
            {"keyword": "adolescent mental health statistics Bandung"},
            {"keyword": "youth mental health survey Yogyakarta"},
            {"keyword": "teen mental health data Medan"},
        ],
        "Gen Z Surveys": [
            {"keyword": "Gen Z mental health survey Indonesia"},
            {"keyword": "Gen Z depression statistics Indonesia"},
            {"keyword": "Gen Z anxiety prevalence Indonesia"},
            {"keyword": "Gen Z suicide rate Indonesia"},
        ],
        "Post-Pandemic Data": [
            {"keyword": "post-pandemic teen mental health survey Indonesia"},
            {"keyword": "post-COVID student mental health statistics Indonesia"},
            {"keyword": "pandemic impact youth mental health data Indonesia"},
            {"keyword": "COVID-19 aftermath teen depression rate Indonesia"},
            {"keyword": "pandemic recovery teen mental health survey Indonesia"},
            {"keyword": "post-pandemic student anxiety statistics Indonesia"},
        ],
    },
    "substance_use": {
        "City-Specific": [
            {"keyword": "teen drug use Jakarta"},
            {"keyword": "student drug abuse Surabaya"},
            {"keyword": "youth substance abuse Bandung"},
            {"keyword": "teen narcotics Yogyakarta"},
            {"keyword": "student drug abuse Medan"},
        ],
        "Vocational Students": [
            {"keyword": "SMK student drug use Indonesia"},
            {"keyword": "vocational school student substance abuse Indonesia"},
            {"keyword": "vocational student vaping Indonesia"},
            {"keyword": "SMK student smoking Indonesia"},
        ],
        "Financial & Gen Z": [
            {"keyword": "Gen Z drug use Indonesia"},
            {"keyword": "Gen Z vaping trend Indonesia"},
            {"keyword": "financial stress teen substance abuse Indonesia"},
            {"keyword": "economic hardship youth drug use Indonesia"},
            {"keyword": "poverty teen substance abuse Indonesia"},
            {"keyword": "unemployment youth drug addiction Indonesia"},
        ],
    },
    "digital_wellbeing": {
        "Online Learning": [
            {"keyword": "online learning anxiety mental health Indonesia"},
            {"keyword": "e-learning stress teen Indonesia"},
            {"keyword": "remote school screen time teen Indonesia"},
            {"keyword": "virtual classroom fatigue student Indonesia"},
            {"keyword": "online exam anxiety student Indonesia"},
        ],
        "Gen Z Digital": [
            {"keyword": "Gen Z social media mental health Indonesia"},
            {"keyword": "Gen Z smartphone addiction Indonesia"},
            {"keyword": "Gen Z digital burnout Indonesia"},
            {"keyword": "Gen Z online identity anxiety Indonesia"},
        ],
        "City-Specific": [
            {"keyword": "teen smartphone addiction Jakarta"},
            {"keyword": "student internet addiction Surabaya"},
            {"keyword": "teen gaming disorder Bandung"},
            {"keyword": "youth social media addiction Yogyakarta"},
            {"keyword": "teen screen time mental health Medan"},
            {"keyword": "student digital wellbeing Medan"},
        ],
    },
    "peer_and_school_environment": {
        "Pesantren Students": [
            {"keyword": "pesantren student mental health Indonesia"},
            {"keyword": "Islamic boarding school student stress Indonesia"},
            {"keyword": "santri mental health Indonesia"},
            {"keyword": "pesantren student bullying Indonesia"},
            {"keyword": "boarding school student loneliness Indonesia"},
        ],
        "Vocational Students": [
            {"keyword": "SMK student bullying Indonesia"},
            {"keyword": "vocational school peer pressure Indonesia"},
            {"keyword": "vocational student social isolation Indonesia"},
            {"keyword": "SMK student school climate Indonesia"},
        ],
        "School Mental Health Program": [
            {"keyword": "school mental health program Indonesia"},
            {"keyword": "school counseling program teen Indonesia"},
            {"keyword": "peer counseling program school Indonesia"},
            {"keyword": "school based mental health intervention Indonesia"},
            {"keyword": "teacher training mental health awareness school Indonesia"},
            {"keyword": "student wellbeing program school Indonesia"},
        ],
    },
    "mental_health_support": {
        "Interventions": [
            {"keyword": "mindfulness program teen Indonesia"},
            {"keyword": "mindfulness therapy student Indonesia"},
            {"keyword": "art therapy teen mental health Indonesia"},
            {"keyword": "art therapy student Indonesia"},
            {"keyword": "peer counseling teen mental health Indonesia"},
            {"keyword": "peer support counseling student Indonesia"},
        ],
        "School Mental Health Program": [
            {"keyword": "school mental health program Indonesia"},
            {"keyword": "school based counseling intervention Indonesia"},
            {"keyword": "teacher mental health training program Indonesia"},
            {"keyword": "student mental health workshop Indonesia"},
        ],
        "City-Specific Support": [
            {"keyword": "teen therapy Jakarta"},
            {"keyword": "student counseling Surabaya"},
            {"keyword": "youth mental health clinic Bandung"},
            {"keyword": "adolescent psychiatric care Yogyakarta"},
            {"keyword": "teen mental health services Medan"},
        ],
    },
    "trauma_and_resilience": {
        "Post-Pandemic": [
            {"keyword": "post-pandemic teen trauma Indonesia"},
            {"keyword": "post-COVID student mental health recovery Indonesia"},
            {"keyword": "pandemic grief teen mental health Indonesia"},
            {"keyword": "COVID-19 loss family teen trauma Indonesia"},
        ],
        "Disaster Survivors": [
            {"keyword": "earthquake survivor teen trauma Indonesia"},
            {"keyword": "tsunami survivor youth PTSD Indonesia"},
            {"keyword": "flood disaster teen mental health Indonesia"},
            {"keyword": "natural disaster survivor student resilience Indonesia"},
            {"keyword": "disaster displaced teen mental health Indonesia"},
        ],
        "Pesantren & Islamic Angle": [
            {"keyword": "pesantren student trauma recovery Indonesia"},
            {"keyword": "Islamic counseling teen mental health Indonesia"},
            {"keyword": "santri resilience program Indonesia"},
            {"keyword": "Islamic boarding school trauma support Indonesia"},
            {"keyword": "pesantren mental health intervention Indonesia"},
            {"keyword": "religious coping teen mental health Indonesia"},
        ],
    },
}

TOPIC_QUERIES_ID: dict[str, dict[str, list[dict]]] = {
    "general_mental_health": {
        "Conditions": [
            {"keyword": "gangguan makan remaja Indonesia"},
            {"keyword": "anoreksia pelajar Indonesia"},
            {"keyword": "bulimia remaja belia Indonesia"},
            {"keyword": "OCD remaja Indonesia"},
            {"keyword": "gangguan obsesif kompulsif pelajar Indonesia"},
            {"keyword": "serangan panik remaja Indonesia"},
            {"keyword": "gangguan panik remaja belia Indonesia"},
            {"keyword": "skizofrenia remaja Indonesia"},
            {"keyword": "psikosis anak muda Indonesia"},
        ],
        "Gen Z & City": [
            {"keyword": "kesehatan mental Gen Z Indonesia"},
            {"keyword": "kesehatan mental Gen Z Jakarta"},
            {"keyword": "kesehatan mental remaja Surabaya"},
            {"keyword": "kesehatan mental remaja Bandung"},
            {"keyword": "kesehatan mental remaja Yogyakarta"},
            {"keyword": "kesehatan mental remaja Medan"},
        ],
    },
    "self_harm_suicide": {
        "City-Specific": [
            {"keyword": "bunuh diri remaja Jakarta"},
            {"keyword": "bunuh diri pelajar Surabaya"},
            {"keyword": "melukai diri remaja Bandung"},
            {"keyword": "bunuh diri pelajar Yogyakarta"},
            {"keyword": "bunuh diri remaja Medan"},
        ],
        "Disaster & Crisis": [
            {"keyword": "risiko bunuh diri remaja penyintas bencana Indonesia"},
            {"keyword": "krisis kesehatan mental remaja penyintas gempa Indonesia"},
            {"keyword": "melukai diri remaja penyintas banjir Indonesia"},
            {"keyword": "bunuh diri anak muda penyintas tsunami Indonesia"},
        ],
        "Financial Stress": [
            {"keyword": "tekanan finansial bunuh diri remaja Indonesia"},
            {"keyword": "tekanan ekonomi bunuh diri pelajar Indonesia"},
            {"keyword": "melukai diri remaja akibat kemiskinan Indonesia"},
            {"keyword": "tekanan utang bunuh diri anak muda Indonesia"},
            {"keyword": "tekanan pengangguran bunuh diri remaja Indonesia"},
            {"keyword": "krisis keuangan keluarga bunuh diri remaja Indonesia"},
        ],
    },
    "academic_social_stressors": {
        "Online Learning": [
            {"keyword": "kecemasan pembelajaran daring Indonesia"},
            {"keyword": "stres belajar jarak jauh pelajar Indonesia"},
            {"keyword": "burnout e-learning remaja Indonesia"},
            {"keyword": "kesehatan mental sekolah daring Indonesia"},
            {"keyword": "kelelahan Zoom pelajar Indonesia"},
        ],
        "Vocational Students": [
            {"keyword": "kesehatan mental siswa SMK Indonesia"},
            {"keyword": "stres siswa sekolah kejuruan Indonesia"},
            {"keyword": "kecemasan siswa SMK Indonesia"},
            {"keyword": "burnout siswa SMK Indonesia"},
        ],
        "Financial Stress": [
            {"keyword": "tekanan finansial pelajar Indonesia"},
            {"keyword": "stres biaya sekolah pelajar Indonesia"},
            {"keyword": "tekanan beasiswa pelajar Indonesia"},
            {"keyword": "stres kerja paruh waktu pelajar Indonesia"},
            {"keyword": "kecemasan ekonomi remaja Indonesia"},
            {"keyword": "tekanan penghasilan keluarga pelajar Indonesia"},
        ],
    },
    "family_domestic_environment": {
        "Migrant Worker Families": [
            {"keyword": "kesehatan mental anak TKI Indonesia"},
            {"keyword": "kesehatan mental anak pekerja migran Indonesia"},
            {"keyword": "kecemasan remaja keluarga pekerja migran Indonesia"},
            {"keyword": "kesehatan mental anak ditinggal orang tua bekerja Indonesia"},
            {"keyword": "depresi remaja keluarga TKI Indonesia"},
        ],
        "Orphan Teens": [
            {"keyword": "kesehatan mental remaja yatim piatu Indonesia"},
            {"keyword": "depresi remaja panti asuhan Indonesia"},
            {"keyword": "trauma remaja yatim piatu Indonesia"},
            {"keyword": "kesehatan mental remaja tanpa orang tua Indonesia"},
        ],
        "Financial Stress": [
            {"keyword": "tekanan finansial keluarga kesehatan mental remaja Indonesia"},
            {"keyword": "kecemasan remaja akibat utang keluarga Indonesia"},
            {"keyword": "depresi remaja keluarga miskin Indonesia"},
            {"keyword": "kesulitan ekonomi remaja yatim piatu Indonesia"},
            {"keyword": "stres remaja keluarga berpenghasilan rendah Indonesia"},
            {"keyword": "ketidakstabilan ekonomi kesehatan mental remaja Indonesia"},
        ],
    },
    "data_surveys_statistics": {
        "City-Specific Surveys": [
            {"keyword": "survei kesehatan mental remaja Jakarta"},
            {"keyword": "data kesehatan mental pelajar Surabaya"},
            {"keyword": "statistik kesehatan mental remaja Bandung"},
            {"keyword": "survei kesehatan mental anak muda Yogyakarta"},
            {"keyword": "data kesehatan mental remaja Medan"},
        ],
        "Gen Z Surveys": [
            {"keyword": "survei kesehatan mental Gen Z Indonesia"},
            {"keyword": "statistik depresi Gen Z Indonesia"},
            {"keyword": "prevalensi kecemasan Gen Z Indonesia"},
            {"keyword": "angka bunuh diri Gen Z Indonesia"},
        ],
        "Post-Pandemic Data": [
            {"keyword": "survei kesehatan mental remaja pasca pandemi Indonesia"},
            {"keyword": "statistik kesehatan mental pelajar pasca-COVID Indonesia"},
            {"keyword": "data kesehatan mental anak muda dampak pandemi Indonesia"},
            {"keyword": "angka depresi remaja pasca COVID-19 Indonesia"},
            {"keyword": "survei kesehatan mental remaja pemulihan pandemi Indonesia"},
            {"keyword": "statistik kecemasan pelajar pasca pandemi Indonesia"},
        ],
    },
    "substance_use": {
        "City-Specific": [
            {"keyword": "penggunaan narkoba remaja Jakarta"},
            {"keyword": "penyalahgunaan narkoba pelajar Surabaya"},
            {"keyword": "penyalahgunaan zat anak muda Bandung"},
            {"keyword": "narkotika remaja Yogyakarta"},
            {"keyword": "penyalahgunaan narkoba pelajar Medan"},
        ],
        "Vocational Students": [
            {"keyword": "penggunaan narkoba siswa SMK Indonesia"},
            {"keyword": "penyalahgunaan zat siswa sekolah kejuruan Indonesia"},
            {"keyword": "vape siswa SMK Indonesia"},
            {"keyword": "merokok siswa SMK Indonesia"},
        ],
        "Financial & Gen Z": [
            {"keyword": "penggunaan narkoba Gen Z Indonesia"},
            {"keyword": "tren vape Gen Z Indonesia"},
            {"keyword": "penyalahgunaan zat remaja akibat tekanan finansial Indonesia"},
            {"keyword": "penggunaan narkoba anak muda akibat kesulitan ekonomi Indonesia"},
            {"keyword": "penyalahgunaan zat remaja akibat kemiskinan Indonesia"},
            {"keyword": "kecanduan narkoba anak muda akibat pengangguran Indonesia"},
        ],
    },
    "digital_wellbeing": {
        "Online Learning": [
            {"keyword": "kesehatan mental kecemasan pembelajaran daring Indonesia"},
            {"keyword": "stres e-learning remaja Indonesia"},
            {"keyword": "waktu layar sekolah daring remaja Indonesia"},
            {"keyword": "kelelahan kelas virtual pelajar Indonesia"},
            {"keyword": "kecemasan ujian daring pelajar Indonesia"},
        ],
        "Gen Z Digital": [
            {"keyword": "kesehatan mental media sosial Gen Z Indonesia"},
            {"keyword": "kecanduan smartphone Gen Z Indonesia"},
            {"keyword": "burnout digital Gen Z Indonesia"},
            {"keyword": "kecemasan identitas daring Gen Z Indonesia"},
        ],
        "City-Specific": [
            {"keyword": "kecanduan smartphone remaja Jakarta"},
            {"keyword": "kecanduan internet pelajar Surabaya"},
            {"keyword": "gangguan bermain gim remaja Bandung"},
            {"keyword": "kecanduan media sosial anak muda Yogyakarta"},
            {"keyword": "kesehatan mental waktu layar remaja Medan"},
            {"keyword": "kesejahteraan digital pelajar Medan"},
        ],
    },
    "peer_and_school_environment": {
        "Pesantren Students": [
            {"keyword": "kesehatan mental santri Indonesia"},
            {"keyword": "stres siswa pondok pesantren Indonesia"},
            {"keyword": "kesehatan mental santri pesantren Indonesia"},
            {"keyword": "perundungan santri pesantren Indonesia"},
            {"keyword": "kesepian siswa pondok pesantren Indonesia"},
        ],
        "Vocational Students": [
            {"keyword": "perundungan siswa SMK Indonesia"},
            {"keyword": "tekanan teman sebaya siswa sekolah kejuruan Indonesia"},
            {"keyword": "isolasi sosial siswa SMK Indonesia"},
            {"keyword": "iklim sekolah siswa SMK Indonesia"},
        ],
        "School Mental Health Program": [
            {"keyword": "program kesehatan mental sekolah Indonesia"},
            {"keyword": "program konseling sekolah remaja Indonesia"},
            {"keyword": "program konseling sebaya sekolah Indonesia"},
            {"keyword": "intervensi kesehatan mental berbasis sekolah Indonesia"},
            {"keyword": "pelatihan guru kesadaran kesehatan mental sekolah Indonesia"},
            {"keyword": "program kesejahteraan siswa sekolah Indonesia"},
        ],
    },
    "mental_health_support": {
        "Interventions": [
            {"keyword": "program mindfulness remaja Indonesia"},
            {"keyword": "terapi mindfulness pelajar Indonesia"},
            {"keyword": "terapi seni kesehatan mental remaja Indonesia"},
            {"keyword": "terapi seni pelajar Indonesia"},
            {"keyword": "konseling sebaya kesehatan mental remaja Indonesia"},
            {"keyword": "dukungan konseling sebaya pelajar Indonesia"},
        ],
        "School Mental Health Program": [
            {"keyword": "program kesehatan mental sekolah Indonesia"},
            {"keyword": "intervensi konseling berbasis sekolah Indonesia"},
            {"keyword": "pelatihan kesehatan mental guru Indonesia"},
            {"keyword": "lokakarya kesehatan mental pelajar Indonesia"},
        ],
        "City-Specific Support": [
            {"keyword": "terapi remaja Jakarta"},
            {"keyword": "konseling pelajar Surabaya"},
            {"keyword": "klinik kesehatan mental anak muda Bandung"},
            {"keyword": "perawatan psikiatri remaja belia Yogyakarta"},
            {"keyword": "layanan kesehatan mental remaja Medan"},
        ],
    },
    "trauma_and_resilience": {
        "Post-Pandemic": [
            {"keyword": "trauma remaja pasca pandemi Indonesia"},
            {"keyword": "pemulihan kesehatan mental pelajar pasca-COVID Indonesia"},
            {"keyword": "kesehatan mental remaja duka pandemi Indonesia"},
            {"keyword": "trauma remaja kehilangan keluarga akibat COVID-19 Indonesia"},
        ],
        "Disaster Survivors": [
            {"keyword": "trauma remaja penyintas gempa Indonesia"},
            {"keyword": "PTSD anak muda penyintas tsunami Indonesia"},
            {"keyword": "kesehatan mental remaja bencana banjir Indonesia"},
            {"keyword": "resiliensi pelajar penyintas bencana alam Indonesia"},
            {"keyword": "kesehatan mental remaja pengungsi bencana Indonesia"},
        ],
        "Pesantren & Islamic Angle": [
            {"keyword": "pemulihan trauma santri pesantren Indonesia"},
            {"keyword": "konseling Islami kesehatan mental remaja Indonesia"},
            {"keyword": "program resiliensi santri Indonesia"},
            {"keyword": "dukungan trauma pondok pesantren Indonesia"},
            {"keyword": "intervensi kesehatan mental pesantren Indonesia"},
            {"keyword": "koping religius kesehatan mental remaja Indonesia"},
        ],
    },
}

GOOGLE_NEWS_RSS_TEMPLATE: str = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
GOOGLE_NEWS_RSS_TEMPLATE_ID: str = "https://news.google.com/rss/search?q={query}&hl=id-ID&gl=ID&ceid=ID:id"

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

MAX_ARTICLES_PER_TOPIC: int = int(os.getenv("MAX_ARTICLES_PER_TOPIC", "5"))
MAX_ARTICLE_AGE_DAYS: int = int(os.getenv("MAX_ARTICLE_AGE_DAYS", "7"))
SCRAPE_DELAY_MIN_SECONDS: float = float(os.getenv("SCRAPE_DELAY_MIN_SECONDS", "1.0"))
SCRAPE_DELAY_MAX_SECONDS: float = float(os.getenv("SCRAPE_DELAY_MAX_SECONDS", "3.0"))

# Embedding — loaded natively in-process (GPU if available) via
# sentence-transformers (dense, BGE) and fastembed (sparse, BM25).
DENSE_MODEL_NAME: str = os.getenv("DENSE_MODEL_NAME", "intfloat/multilingual-e5-large")
SPARSE_MODEL_NAME: str = os.getenv("SPARSE_MODEL_NAME", "Qdrant/bm25")
BGE_QUERY_INSTRUCTION: str = os.getenv("BGE_QUERY_INSTRUCTION", "query: ")
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "1024"))

# Reranking — cross-encoder applied to RRF's fused candidates before they
# reach the generator (see backend/retrieval/searcher.py).
RERANKER_MODEL_NAME: str = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
RERANKER_TOP_K: int = int(os.getenv("RERANKER_TOP_K", "5"))

# Generation — all LLM calls go through OpenRouter (OpenAI-compatible API).
# Three roles use three different models (see paper methodology notes):
#   DATASET_GENERATOR_MODEL -> evaluation/generate_dataset.py
#   RAG_GENERATOR_MODEL     -> rag/generator.py, backend/generation/generator.py
#   JUDGE_MODEL             -> evaluation/evaluate.py (RAGAS + DeepEval)
#   GUARDRAIL_MODEL         -> backend/guardrails/input.py (scope/language)
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DATASET_GENERATOR_MODEL: str = os.getenv("DATASET_GENERATOR_MODEL", "openai/gpt-4o-mini")
RAG_GENERATOR_MODEL: str = os.getenv("RAG_GENERATOR_MODEL", "deepseek/deepseek-chat-v3-0324")
JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "google/gemini-2.5-flash")
GUARDRAIL_MODEL: str = os.getenv("GUARDRAIL_MODEL", "openai/gpt-4o-mini")

# OpenRouter provider slugs to pin per role (e.g. the host serving deepseek-chat-v3-0324).
# Empty = no pin, so OpenRouter may route each request to any provider. Set these for
# reproducible evaluation runs and record them in results.csv.
DATASET_GENERATOR_PROVIDER: str = os.getenv("DATASET_GENERATOR_PROVIDER", "")
RAG_GENERATOR_PROVIDER: str = os.getenv("RAG_GENERATOR_PROVIDER", "")
JUDGE_PROVIDER: str = os.getenv("JUDGE_PROVIDER", "")
GUARDRAIL_PROVIDER: str = os.getenv("GUARDRAIL_PROVIDER", "")


def provider_body(provider_slug: str) -> dict:
    """Return the OpenRouter provider-routing fragment for a request body.

    An empty slug returns {} (no pin). A non-empty slug pins the request to that
    provider and disables fallback, so a silent reroute fails loudly instead of
    changing the model's serving stack mid-evaluation.

    Args:
        provider_slug: OpenRouter provider name, e.g. as shown on the model's page.

    Returns:
        {"provider": {...}} or {}.
    """
    if not provider_slug:
        return {}
    return {"provider": {"order": [provider_slug], "allow_fallbacks": False}}

QDRANT_COLLECTION: str = os.getenv("COLLECTION_NAME", "data-paper-child")

CHUNK_SIZE_TOKENS: int = 500
CHUNK_OVERLAP_TOKENS: int = 50
MIN_CONTENT_LENGTH: int = 100

RETRIEVAL_TOP_K: int = 5
CONVERSATION_HISTORY_LIMIT: int = 10

DATA_RAW_DIR: str = os.path.join(os.path.dirname(__file__), "data", "raw")
DATA_CLEAN_DIR: str = os.path.join(os.path.dirname(__file__), "data", "clean")
DATA_CHUNKS_DIR: str = os.path.join(os.path.dirname(__file__), "data", "chunks")
DATA_PDF_DIR: str = os.path.join(os.path.dirname(__file__), "data", "pdf")