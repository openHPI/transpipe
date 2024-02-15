from django.core.exceptions import PermissionDenied

from mooclink.services.status_change_service import SubtitleStatusChangeService
from subtitles.models import IsoLanguage, SubtitleAssignment
from subtitles.models.translation_service import TranslationService

_SUPPORTED_TRANSCRIPTION_LANGUAGES = {
    TranslationService.AWS: [
        'ar',
        'de',
        'en',
        'es',
        'fa',
        'fr',
        'he',
        'hi',
        'id',
        'it',
        'ja',
        'ko',
        'ms',
        'nl',
        'pt',
        'ru',
        'ta',
        'te',
        'tr',
        'zh',
    ],
    TranslationService.MLLP: [
        'de',
        'dk',
        'ee',
        'en',
        'es',
        'fr',
        'it',
        'pt',
        'sl'
    ],
    TranslationService.DEEPL: [
        'bg',
        'cs',
        'da',
        'de',
        'el',
        'en',
        'en-gb',
        'en-us',
        'es',
        'et',
        'fi',
        'fr',
        'hu',
        'id',
        'it',
        'ja',
        'lt',
        'lv',
        'nl',
        'pl',
        'pt',
        'pt-br',
        'pt-pt',
        'ro',
        'ru',
        'sk',
        'sl',
        'sv',
        'tr',
        'uk',
        'zh',
    ]
}

AWS_TRANSCRIBE_SUPPORTED = {"en-IE", "ar-AE", "te-IN", "zh-TW", "en-US", "ta-IN", "en-AB", "en-IN", "zh-CN", "ar-SA",
                            "en-ZA", "gd-GB", "th-TH", "tr-TR", "ru-RU", "pt-PT", "nl-NL", "it-IT", "id-ID", "fr-FR",
                            "es-ES", "de-DE", "ga-IE", "af-ZA", "en-NZ", "ko-KR", "hi-IN", "de-CH", "cy-GB", "ms-MY",
                            "he-IL", "da-DK", "en-AU", "pt-BR", "en-WL", "fa-IR", "ja-JP", "es-US", "fr-CA", "en-GB"}

MAPPING_SLIM_TO_FULL = {
    'ar': "ar-AE",
    'da': "da-DK",
    'de': "de-DE",
    'en': "en-US",
    'es': "es-ES",
    'fr': "fr-FR",
    'hi': "hi-IN",
    'id': "id-ID",
    'it': "it-IT",
    'ja': "ja-JP",
    'ko': "ko-KR",
    'ms': "ms-MY",
    'nl': "nl-NL",
    'pt': "pt-PT",
    'ru': "ru-RU",
    'ta': "ta-IN",
    'zh': "zh-CN",
}


def get_supported_languages(service=None):
    query = IsoLanguage.objects

    if service and service != TranslationService.MANUAL:
        query = query.filter(iso_code__in=_SUPPORTED_TRANSCRIPTION_LANGUAGES[service])

    return query\
        .distinct() \
        .order_by('description') \
        .all()


subtitle_status_change_service = SubtitleStatusChangeService()


def can_user_view_video(request, video, raise_ex=True):
    if request.user.has_perm('core.can_see_all_courses') or \
            SubtitleAssignment.objects.filter(subtitle__video=video).exists():
        return True

    if raise_ex:
        raise PermissionDenied("You do not have permission to access this video.")

    return False
