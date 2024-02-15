"""Form handling in TransPipe"""
import io
import mimetypes

from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, reverse
from django.contrib import messages
