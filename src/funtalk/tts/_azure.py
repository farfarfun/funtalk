import os
import re
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

from edge_tts import SubMaker
from farlog import getLogger

from funtalk._util import convert_rate_to_percent

from .base import BaseTTS

logger = getLogger("funtalk")

_LOCALE_PREFIX = re.compile(r"^([a-zA-Z]{2,3}-[a-zA-Z]{2,})-")


def _locale_from_voice_name(voice_name: str, default: str = "zh-CN") -> str:
    """从 Azure 语音名称推断 SSML 所需的 `xml:lang` 区域代码。

    Args:
        voice_name: Azure 语音名称，例如 ``"zh-CN-XiaoxiaoNeural"``。
        default: 无法识别时使用的回退区域代码。

    Returns:
        形如 ``"zh-CN"`` 的区域代码；无法识别前缀时返回 `default`。
    """
    match = _LOCALE_PREFIX.match(voice_name)
    return match.group(1) if match else default


class AzureSynthesisError(RuntimeError):
    """Azure 语音合成失败时抛出的领域异常。"""


class AzureTTS(BaseTTS):
    """基于 Azure Speech SDK 的语音合成实现。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化 Azure TTS 客户端。"""
        super().__init__(*args, **kwargs)

    def get_all_voice_name(self, filter_locals: list[str] | None = None) -> list[str]:
        """返回指定区域的 Azure 语音名称列表。"""
        if filter_locals is None:
            filter_locals = ["zh-CN", "en-US", "zh-HK", "zh-TW", "vi-VN"]
        voices_str = """
        Name: af-ZA-AdriNeural
        Gender: Female
        
        Name: af-ZA-WillemNeural
        Gender: Male
        
        Name: am-ET-AmehaNeural
        Gender: Male
        
        Name: am-ET-MekdesNeural
        Gender: Female
        
        Name: ar-AE-FatimaNeural
        Gender: Female
        
        Name: ar-AE-HamdanNeural
        Gender: Male
        
        Name: ar-BH-AliNeural
        Gender: Male
        
        Name: ar-BH-LailaNeural
        Gender: Female
        
        Name: ar-DZ-AminaNeural
        Gender: Female
        
        Name: ar-DZ-IsmaelNeural
        Gender: Male
        
        Name: ar-EG-SalmaNeural
        Gender: Female
        
        Name: ar-EG-ShakirNeural
        Gender: Male
        
        Name: ar-IQ-BasselNeural
        Gender: Male
        
        Name: ar-IQ-RanaNeural
        Gender: Female
        
        Name: ar-JO-SanaNeural
        Gender: Female
        
        Name: ar-JO-TaimNeural
        Gender: Male
        
        Name: ar-KW-FahedNeural
        Gender: Male
        
        Name: ar-KW-NouraNeural
        Gender: Female
        
        Name: ar-LB-LaylaNeural
        Gender: Female
        
        Name: ar-LB-RamiNeural
        Gender: Male
        
        Name: ar-LY-ImanNeural
        Gender: Female
        
        Name: ar-LY-OmarNeural
        Gender: Male
        
        Name: ar-MA-JamalNeural
        Gender: Male
        
        Name: ar-MA-MounaNeural
        Gender: Female
        
        Name: ar-OM-AbdullahNeural
        Gender: Male
        
        Name: ar-OM-AyshaNeural
        Gender: Female
        
        Name: ar-QA-AmalNeural
        Gender: Female
        
        Name: ar-QA-MoazNeural
        Gender: Male
        
        Name: ar-SA-HamedNeural
        Gender: Male
        
        Name: ar-SA-ZariyahNeural
        Gender: Female
        
        Name: ar-SY-AmanyNeural
        Gender: Female
        
        Name: ar-SY-LaithNeural
        Gender: Male
        
        Name: ar-TN-HediNeural
        Gender: Male
        
        Name: ar-TN-ReemNeural
        Gender: Female
        
        Name: ar-YE-MaryamNeural
        Gender: Female
        
        Name: ar-YE-SalehNeural
        Gender: Male
        
        Name: az-AZ-BabekNeural
        Gender: Male
        
        Name: az-AZ-BanuNeural
        Gender: Female
        
        Name: bg-BG-BorislavNeural
        Gender: Male
        
        Name: bg-BG-KalinaNeural
        Gender: Female
        
        Name: bn-BD-NabanitaNeural
        Gender: Female
        
        Name: bn-BD-PradeepNeural
        Gender: Male
        
        Name: bn-IN-BashkarNeural
        Gender: Male
        
        Name: bn-IN-TanishaaNeural
        Gender: Female
        
        Name: bs-BA-GoranNeural
        Gender: Male
        
        Name: bs-BA-VesnaNeural
        Gender: Female
        
        Name: ca-ES-EnricNeural
        Gender: Male
        
        Name: ca-ES-JoanaNeural
        Gender: Female
        
        Name: cs-CZ-AntoninNeural
        Gender: Male
        
        Name: cs-CZ-VlastaNeural
        Gender: Female
        
        Name: cy-GB-AledNeural
        Gender: Male
        
        Name: cy-GB-NiaNeural
        Gender: Female
        
        Name: da-DK-ChristelNeural
        Gender: Female
        
        Name: da-DK-JeppeNeural
        Gender: Male
        
        Name: de-AT-IngridNeural
        Gender: Female
        
        Name: de-AT-JonasNeural
        Gender: Male
        
        Name: de-CH-JanNeural
        Gender: Male
        
        Name: de-CH-LeniNeural
        Gender: Female
        
        Name: de-DE-AmalaNeural
        Gender: Female
        
        Name: de-DE-ConradNeural
        Gender: Male
        
        Name: de-DE-FlorianMultilingualNeural
        Gender: Male
        
        Name: de-DE-KatjaNeural
        Gender: Female
        
        Name: de-DE-KillianNeural
        Gender: Male
        
        Name: de-DE-SeraphinaMultilingualNeural
        Gender: Female
        
        Name: el-GR-AthinaNeural
        Gender: Female
        
        Name: el-GR-NestorasNeural
        Gender: Male
        
        Name: en-AU-NatashaNeural
        Gender: Female
        
        Name: en-AU-WilliamNeural
        Gender: Male
        
        Name: en-CA-ClaraNeural
        Gender: Female
        
        Name: en-CA-LiamNeural
        Gender: Male
        
        Name: en-GB-LibbyNeural
        Gender: Female
        
        Name: en-GB-MaisieNeural
        Gender: Female
        
        Name: en-GB-RyanNeural
        Gender: Male
        
        Name: en-GB-SoniaNeural
        Gender: Female
        
        Name: en-GB-ThomasNeural
        Gender: Male
        
        Name: en-HK-SamNeural
        Gender: Male
        
        Name: en-HK-YanNeural
        Gender: Female
        
        Name: en-IE-ConnorNeural
        Gender: Male
        
        Name: en-IE-EmilyNeural
        Gender: Female
        
        Name: en-IN-NeerjaExpressiveNeural
        Gender: Female
        
        Name: en-IN-NeerjaNeural
        Gender: Female
        
        Name: en-IN-PrabhatNeural
        Gender: Male
        
        Name: en-KE-AsiliaNeural
        Gender: Female
        
        Name: en-KE-ChilembaNeural
        Gender: Male
        
        Name: en-NG-AbeoNeural
        Gender: Male
        
        Name: en-NG-EzinneNeural
        Gender: Female
        
        Name: en-NZ-MitchellNeural
        Gender: Male
        
        Name: en-NZ-MollyNeural
        Gender: Female
        
        Name: en-PH-JamesNeural
        Gender: Male
        
        Name: en-PH-RosaNeural
        Gender: Female
        
        Name: en-SG-LunaNeural
        Gender: Female
        
        Name: en-SG-WayneNeural
        Gender: Male
        
        Name: en-TZ-ElimuNeural
        Gender: Male
        
        Name: en-TZ-ImaniNeural
        Gender: Female
        
        Name: en-US-AnaNeural
        Gender: Female
        
        Name: en-US-AndrewNeural
        Gender: Male
        
        Name: en-US-AriaNeural
        Gender: Female
        
        Name: en-US-AvaNeural
        Gender: Female
        
        Name: en-US-BrianNeural
        Gender: Male
        
        Name: en-US-ChristopherNeural
        Gender: Male
        
        Name: en-US-EmmaNeural
        Gender: Female
        
        Name: en-US-EricNeural
        Gender: Male
        
        Name: en-US-GuyNeural
        Gender: Male
        
        Name: en-US-JennyNeural
        Gender: Female
        
        Name: en-US-MichelleNeural
        Gender: Female
        
        Name: en-US-RogerNeural
        Gender: Male
        
        Name: en-US-SteffanNeural
        Gender: Male
        
        Name: en-ZA-LeahNeural
        Gender: Female
        
        Name: en-ZA-LukeNeural
        Gender: Male
        
        Name: es-AR-ElenaNeural
        Gender: Female
        
        Name: es-AR-TomasNeural
        Gender: Male
        
        Name: es-BO-MarceloNeural
        Gender: Male
        
        Name: es-BO-SofiaNeural
        Gender: Female
        
        Name: es-CL-CatalinaNeural
        Gender: Female
        
        Name: es-CL-LorenzoNeural
        Gender: Male
        
        Name: es-CO-GonzaloNeural
        Gender: Male
        
        Name: es-CO-SalomeNeural
        Gender: Female
        
        Name: es-CR-JuanNeural
        Gender: Male
        
        Name: es-CR-MariaNeural
        Gender: Female
        
        Name: es-CU-BelkysNeural
        Gender: Female
        
        Name: es-CU-ManuelNeural
        Gender: Male
        
        Name: es-DO-EmilioNeural
        Gender: Male
        
        Name: es-DO-RamonaNeural
        Gender: Female
        
        Name: es-EC-AndreaNeural
        Gender: Female
        
        Name: es-EC-LuisNeural
        Gender: Male
        
        Name: es-ES-AlvaroNeural
        Gender: Male
        
        Name: es-ES-ElviraNeural
        Gender: Female
        
        Name: es-ES-XimenaNeural
        Gender: Female
        
        Name: es-GQ-JavierNeural
        Gender: Male
        
        Name: es-GQ-TeresaNeural
        Gender: Female
        
        Name: es-GT-AndresNeural
        Gender: Male
        
        Name: es-GT-MartaNeural
        Gender: Female
        
        Name: es-HN-CarlosNeural
        Gender: Male
        
        Name: es-HN-KarlaNeural
        Gender: Female
        
        Name: es-MX-DaliaNeural
        Gender: Female
        
        Name: es-MX-JorgeNeural
        Gender: Male
        
        Name: es-NI-FedericoNeural
        Gender: Male
        
        Name: es-NI-YolandaNeural
        Gender: Female
        
        Name: es-PA-MargaritaNeural
        Gender: Female
        
        Name: es-PA-RobertoNeural
        Gender: Male
        
        Name: es-PE-AlexNeural
        Gender: Male
        
        Name: es-PE-CamilaNeural
        Gender: Female
        
        Name: es-PR-KarinaNeural
        Gender: Female
        
        Name: es-PR-VictorNeural
        Gender: Male
        
        Name: es-PY-MarioNeural
        Gender: Male
        
        Name: es-PY-TaniaNeural
        Gender: Female
        
        Name: es-SV-LorenaNeural
        Gender: Female
        
        Name: es-SV-RodrigoNeural
        Gender: Male
        
        Name: es-US-AlonsoNeural
        Gender: Male
        
        Name: es-US-PalomaNeural
        Gender: Female
        
        Name: es-UY-MateoNeural
        Gender: Male
        
        Name: es-UY-ValentinaNeural
        Gender: Female
        
        Name: es-VE-PaolaNeural
        Gender: Female
        
        Name: es-VE-SebastianNeural
        Gender: Male
        
        Name: et-EE-AnuNeural
        Gender: Female
        
        Name: et-EE-KertNeural
        Gender: Male
        
        Name: fa-IR-DilaraNeural
        Gender: Female
        
        Name: fa-IR-FaridNeural
        Gender: Male
        
        Name: fi-FI-HarriNeural
        Gender: Male
        
        Name: fi-FI-NooraNeural
        Gender: Female
        
        Name: fil-PH-AngeloNeural
        Gender: Male
        
        Name: fil-PH-BlessicaNeural
        Gender: Female
        
        Name: fr-BE-CharlineNeural
        Gender: Female
        
        Name: fr-BE-GerardNeural
        Gender: Male
        
        Name: fr-CA-AntoineNeural
        Gender: Male
        
        Name: fr-CA-JeanNeural
        Gender: Male
        
        Name: fr-CA-SylvieNeural
        Gender: Female
        
        Name: fr-CA-ThierryNeural
        Gender: Male
        
        Name: fr-CH-ArianeNeural
        Gender: Female
        
        Name: fr-CH-FabriceNeural
        Gender: Male
        
        Name: fr-FR-DeniseNeural
        Gender: Female
        
        Name: fr-FR-EloiseNeural
        Gender: Female
        
        Name: fr-FR-HenriNeural
        Gender: Male
        
        Name: fr-FR-RemyMultilingualNeural
        Gender: Male
        
        Name: fr-FR-VivienneMultilingualNeural
        Gender: Female
        
        Name: ga-IE-ColmNeural
        Gender: Male
        
        Name: ga-IE-OrlaNeural
        Gender: Female
        
        Name: gl-ES-RoiNeural
        Gender: Male
        
        Name: gl-ES-SabelaNeural
        Gender: Female
        
        Name: gu-IN-DhwaniNeural
        Gender: Female
        
        Name: gu-IN-NiranjanNeural
        Gender: Male
        
        Name: he-IL-AvriNeural
        Gender: Male
        
        Name: he-IL-HilaNeural
        Gender: Female
        
        Name: hi-IN-MadhurNeural
        Gender: Male
        
        Name: hi-IN-SwaraNeural
        Gender: Female
        
        Name: hr-HR-GabrijelaNeural
        Gender: Female
        
        Name: hr-HR-SreckoNeural
        Gender: Male
        
        Name: hu-HU-NoemiNeural
        Gender: Female
        
        Name: hu-HU-TamasNeural
        Gender: Male
        
        Name: id-ID-ArdiNeural
        Gender: Male
        
        Name: id-ID-GadisNeural
        Gender: Female
        
        Name: is-IS-GudrunNeural
        Gender: Female
        
        Name: is-IS-GunnarNeural
        Gender: Male
        
        Name: it-IT-DiegoNeural
        Gender: Male
        
        Name: it-IT-ElsaNeural
        Gender: Female
        
        Name: it-IT-GiuseppeNeural
        Gender: Male
        
        Name: it-IT-IsabellaNeural
        Gender: Female
        
        Name: ja-JP-KeitaNeural
        Gender: Male
        
        Name: ja-JP-NanamiNeural
        Gender: Female
        
        Name: jv-ID-DimasNeural
        Gender: Male
        
        Name: jv-ID-SitiNeural
        Gender: Female
        
        Name: ka-GE-EkaNeural
        Gender: Female
        
        Name: ka-GE-GiorgiNeural
        Gender: Male
        
        Name: kk-KZ-AigulNeural
        Gender: Female
        
        Name: kk-KZ-DauletNeural
        Gender: Male
        
        Name: km-KH-PisethNeural
        Gender: Male
        
        Name: km-KH-SreymomNeural
        Gender: Female
        
        Name: kn-IN-GaganNeural
        Gender: Male
        
        Name: kn-IN-SapnaNeural
        Gender: Female
        
        Name: ko-KR-HyunsuNeural
        Gender: Male
        
        Name: ko-KR-InJoonNeural
        Gender: Male
        
        Name: ko-KR-SunHiNeural
        Gender: Female
        
        Name: lo-LA-ChanthavongNeural
        Gender: Male
        
        Name: lo-LA-KeomanyNeural
        Gender: Female
        
        Name: lt-LT-LeonasNeural
        Gender: Male
        
        Name: lt-LT-OnaNeural
        Gender: Female
        
        Name: lv-LV-EveritaNeural
        Gender: Female
        
        Name: lv-LV-NilsNeural
        Gender: Male
        
        Name: mk-MK-AleksandarNeural
        Gender: Male
        
        Name: mk-MK-MarijaNeural
        Gender: Female
        
        Name: ml-IN-MidhunNeural
        Gender: Male
        
        Name: ml-IN-SobhanaNeural
        Gender: Female
        
        Name: mn-MN-BataaNeural
        Gender: Male
        
        Name: mn-MN-YesuiNeural
        Gender: Female
        
        Name: mr-IN-AarohiNeural
        Gender: Female
        
        Name: mr-IN-ManoharNeural
        Gender: Male
        
        Name: ms-MY-OsmanNeural
        Gender: Male
        
        Name: ms-MY-YasminNeural
        Gender: Female
        
        Name: mt-MT-GraceNeural
        Gender: Female
        
        Name: mt-MT-JosephNeural
        Gender: Male
        
        Name: my-MM-NilarNeural
        Gender: Female
        
        Name: my-MM-ThihaNeural
        Gender: Male
        
        Name: nb-NO-FinnNeural
        Gender: Male
        
        Name: nb-NO-PernilleNeural
        Gender: Female
        
        Name: ne-NP-HemkalaNeural
        Gender: Female
        
        Name: ne-NP-SagarNeural
        Gender: Male
        
        Name: nl-BE-ArnaudNeural
        Gender: Male
        
        Name: nl-BE-DenaNeural
        Gender: Female
        
        Name: nl-NL-ColetteNeural
        Gender: Female
        
        Name: nl-NL-FennaNeural
        Gender: Female
        
        Name: nl-NL-MaartenNeural
        Gender: Male
        
        Name: pl-PL-MarekNeural
        Gender: Male
        
        Name: pl-PL-ZofiaNeural
        Gender: Female
        
        Name: ps-AF-GulNawazNeural
        Gender: Male
        
        Name: ps-AF-LatifaNeural
        Gender: Female
        
        Name: pt-BR-AntonioNeural
        Gender: Male
        
        Name: pt-BR-FranciscaNeural
        Gender: Female
        
        Name: pt-BR-ThalitaNeural
        Gender: Female
        
        Name: pt-PT-DuarteNeural
        Gender: Male
        
        Name: pt-PT-RaquelNeural
        Gender: Female
        
        Name: ro-RO-AlinaNeural
        Gender: Female
        
        Name: ro-RO-EmilNeural
        Gender: Male
        
        Name: ru-RU-DmitryNeural
        Gender: Male
        
        Name: ru-RU-SvetlanaNeural
        Gender: Female
        
        Name: si-LK-SameeraNeural
        Gender: Male
        
        Name: si-LK-ThiliniNeural
        Gender: Female
        
        Name: sk-SK-LukasNeural
        Gender: Male
        
        Name: sk-SK-ViktoriaNeural
        Gender: Female
        
        Name: sl-SI-PetraNeural
        Gender: Female
        
        Name: sl-SI-RokNeural
        Gender: Male
        
        Name: so-SO-MuuseNeural
        Gender: Male
        
        Name: so-SO-UbaxNeural
        Gender: Female
        
        Name: sq-AL-AnilaNeural
        Gender: Female
        
        Name: sq-AL-IlirNeural
        Gender: Male
        
        Name: sr-RS-NicholasNeural
        Gender: Male
        
        Name: sr-RS-SophieNeural
        Gender: Female
        
        Name: su-ID-JajangNeural
        Gender: Male
        
        Name: su-ID-TutiNeural
        Gender: Female
        
        Name: sv-SE-MattiasNeural
        Gender: Male
        
        Name: sv-SE-SofieNeural
        Gender: Female
        
        Name: sw-KE-RafikiNeural
        Gender: Male
        
        Name: sw-KE-ZuriNeural
        Gender: Female
        
        Name: sw-TZ-DaudiNeural
        Gender: Male
        
        Name: sw-TZ-RehemaNeural
        Gender: Female
        
        Name: ta-IN-PallaviNeural
        Gender: Female
        
        Name: ta-IN-ValluvarNeural
        Gender: Male
        
        Name: ta-LK-KumarNeural
        Gender: Male
        
        Name: ta-LK-SaranyaNeural
        Gender: Female
        
        Name: ta-MY-KaniNeural
        Gender: Female
        
        Name: ta-MY-SuryaNeural
        Gender: Male
        
        Name: ta-SG-AnbuNeural
        Gender: Male
        
        Name: ta-SG-VenbaNeural
        Gender: Female
        
        Name: te-IN-MohanNeural
        Gender: Male
        
        Name: te-IN-ShrutiNeural
        Gender: Female
        
        Name: th-TH-NiwatNeural
        Gender: Male
        
        Name: th-TH-PremwadeeNeural
        Gender: Female
        
        Name: tr-TR-AhmetNeural
        Gender: Male
        
        Name: tr-TR-EmelNeural
        Gender: Female
        
        Name: uk-UA-OstapNeural
        Gender: Male
        
        Name: uk-UA-PolinaNeural
        Gender: Female
        
        Name: ur-IN-GulNeural
        Gender: Female
        
        Name: ur-IN-SalmanNeural
        Gender: Male
        
        Name: ur-PK-AsadNeural
        Gender: Male
        
        Name: ur-PK-UzmaNeural
        Gender: Female
        
        Name: uz-UZ-MadinaNeural
        Gender: Female
        
        Name: uz-UZ-SardorNeural
        Gender: Male
        
        Name: vi-VN-HoaiMyNeural
        Gender: Female
        
        Name: vi-VN-NamMinhNeural
        Gender: Male
        
        Name: zh-CN-XiaoxiaoNeural
        Gender: Female
        
        Name: zh-CN-XiaoyiNeural
        Gender: Female
        
        Name: zh-CN-YunjianNeural
        Gender: Male
        
        Name: zh-CN-YunxiNeural
        Gender: Male
        
        Name: zh-CN-YunxiaNeural
        Gender: Male
        
        Name: zh-CN-YunyangNeural
        Gender: Male
        
        Name: zh-CN-liaoning-XiaobeiNeural
        Gender: Female
        
        Name: zh-CN-shaanxi-XiaoniNeural
        Gender: Female
        
        Name: zh-HK-HiuGaaiNeural
        Gender: Female
        
        Name: zh-HK-HiuMaanNeural
        Gender: Female
        
        Name: zh-HK-WanLungNeural
        Gender: Male
        
        Name: zh-TW-HsiaoChenNeural
        Gender: Female
        
        Name: zh-TW-HsiaoYuNeural
        Gender: Female
        
        Name: zh-TW-YunJheNeural
        Gender: Male
        
        Name: zu-ZA-ThandoNeural
        Gender: Female
        
        Name: zu-ZA-ThembaNeural
        Gender: Male
        
        
        Name: en-US-AvaMultilingualNeural-V2
        Gender: Female
        
        Name: en-US-AndrewMultilingualNeural-V2
        Gender: Male
        
        Name: en-US-EmmaMultilingualNeural-V2
        Gender: Female
        
        Name: en-US-BrianMultilingualNeural-V2
        Gender: Male
        
        Name: de-DE-FlorianMultilingualNeural-V2
        Gender: Male
        
        Name: de-DE-SeraphinaMultilingualNeural-V2
        Gender: Female
        
        Name: fr-FR-RemyMultilingualNeural-V2
        Gender: Male
        
        Name: fr-FR-VivienneMultilingualNeural-V2
        Gender: Female
    
        Name: zh-CN-XiaoxiaoMultilingualNeural-V2
        Gender: Female
        """.strip()
        voices = []
        name = ""
        for line in voices_str.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("Name: "):
                name = line[6:].strip()
            if line.startswith("Gender: "):
                gender = line[8:].strip()
                if name and gender:
                    # voices.append({
                    #     "name": name,
                    #     "gender": gender,
                    # })
                    if filter_locals:
                        for filter_local in filter_locals:
                            if name.lower().startswith(filter_local.lower()):
                                voices.append(f"{name}-{gender}")
                    else:
                        voices.append(f"{name}-{gender}")
                    name = ""
        voices.sort()
        return voices

    @staticmethod
    def check(voice_name: str) -> str:
        """移除 Azure V2 语音名称的版本后缀。"""
        if voice_name.endswith("-V2"):
            return voice_name.replace("-V2", "").strip()
        return voice_name

    def _tts(
        self,
        text: str,
        voice_rate: float,
        voice_file: str,
        *args: Any,
        **kwargs: Any,
    ) -> SubMaker:
        voice_name = self.check(self.voice_name)
        if not voice_name:
            logger.error(f"invalid voice name: {voice_name}")
            raise ValueError(f"invalid voice name: {voice_name}")
        text = text.strip()

        def _format_duration_to_offset(duration: str | int) -> int:
            if isinstance(duration, str):
                time_obj = datetime.strptime(duration, "%H:%M:%S.%f")
                milliseconds = (
                    (time_obj.hour * 3600000)
                    + (time_obj.minute * 60000)
                    + (time_obj.second * 1000)
                    + (time_obj.microsecond // 1000)
                )
                return milliseconds * 10000

            if isinstance(duration, int):
                return duration

            return 0

        logger.info(f"start, voice name: {voice_name}")
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise AzureSynthesisError("未安装 Azure Speech SDK") from exc

        sub_maker = SubMaker()

        def speech_synthesizer_word_boundary_cb(
            evt: speechsdk.SessionEventArgs,
        ) -> None:

            duration = _format_duration_to_offset(str(evt.duration))
            offset = _format_duration_to_offset(evt.audio_offset)
            sub_maker.subs.append(evt.text)
            sub_maker.offset.append((offset, offset + duration))

        # 使用订阅密钥和服务区域创建语音配置。
        speech_key = os.environ.get("AZURE_SPEECH_KEY", "")
        service_region = os.environ.get("AZURE_SPEECH_REGION", "")
        try:
            audio_config = speechsdk.audio.AudioOutputConfig(
                filename=voice_file, use_default_speaker=True
            )
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key, region=service_region
            )
            speech_config.speech_synthesis_voice_name = voice_name
            speech_config.set_property(
                property_id=speechsdk.PropertyId.SpeechServiceResponse_RequestWordBoundary,
                value="true",
            )

            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3
            )
            speech_synthesizer = speechsdk.SpeechSynthesizer(
                audio_config=audio_config, speech_config=speech_config
            )
            speech_synthesizer.synthesis_word_boundary.connect(
                speech_synthesizer_word_boundary_cb
            )

            # 必须用 SSML 的 <prosody rate="..."> 承载语速，speak_text_async
            # 不接受语速参数——此前直接调用 speak_text_async(text) 会让
            # voice_rate 形参被静默忽略，合成结果恒为默认语速。
            rate_str = convert_rate_to_percent(voice_rate)
            locale = _locale_from_voice_name(voice_name)
            ssml = (
                f'<speak version="1.0" '
                f'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
                f'<voice name="{voice_name}">'
                f'<prosody rate="{rate_str}">{escape(text)}</prosody>'
                f"</voice></speak>"
            )
            result = speech_synthesizer.speak_ssml_async(ssml).get()
        except (OSError, RuntimeError, ValueError) as exc:
            raise AzureSynthesisError(
                f"Azure 语音合成调用失败：{voice_file}"
            ) from exc

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.success(f"azure v2 speech synthesis succeeded: {voice_file}")
            return sub_maker
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            message = f"Azure 语音合成已取消：{details.reason}"
            if details.reason == speechsdk.CancellationReason.Error:
                message += f"，{details.error_details}"
            raise AzureSynthesisError(message)
        raise AzureSynthesisError(f"Azure 语音合成返回未知状态：{result.reason}")


def tts_generate(
    text: str, voice_name: str, voice_rate: float, voice_file: str, subtitle_file: str
) -> BaseTTS:
    """合成语音并返回 Azure TTS 客户端。

    Args:
        text: 待合成的文本。
        voice_name: Azure 语音名称，例如 ``"zh-CN-XiaoxiaoNeural"``；允许带
            `-Female`/`-Male`/`-V2` 后缀，内部会自动归一化。
        voice_rate: 语速倍率，1.0 为正常语速，通过 SSML `<prosody rate="...">` 生效。
        voice_file: 合成音频的输出路径。
        subtitle_file: 对齐字幕的输出路径；生成字幕依赖可选依赖 ``funtalk[tts]``
            （moviepy），未安装时会抛出 `SubtitleGenerationError`。

    Returns:
        已完成合成的 `AzureTTS` 客户端实例，可通过 `client.sub_maker` 获取字幕时间戳。

    Raises:
        AzureSynthesisError: 缺少 Azure Speech SDK、调用失败或合成被取消时抛出。
    """
    client = AzureTTS(voice_name=voice_name)
    client.create_tts(
        text=text,
        voice_rate=voice_rate,
        voice_file=voice_file,
        subtitle_file=subtitle_file,
    )
    return client
