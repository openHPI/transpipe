"""
Models module in our pipeline project.

"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from .awsupload import AWSupload
from .comment import Comment
from .course import Course
from .assigned_language import AssignedLanguage
from .course_section import CourseSection
from .subtitle import Subtitle
from .video import Video
from .subtitle import Subtitle
from .subtitle_file import SubtitleFile
from .iso_language import IsoLanguage
from .subtitle_assignment import SubtitleAssignment
from .service_provider_use import ServiceProviderUse
