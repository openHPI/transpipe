import datetime

from django.test import TestCase
from django.utils import timezone

from .models import Course


class CourseModelTests(TestCase):
    def test_number_of_videos(self):
        """
        create course
        number_of_videos should be 0
        add a video
        number_of_videos should be 1
        """
        course1 = Course(
            title="test course",
            abstract="test course abstract",
            start_date=timezone.now() + datetime.timedelta(days=7),
            end_date=timezone.now() + datetime.timedelta(days=30),
        )
        video_count = course1.number_of_videos
        self.assertIs(video_count == 0, True)
