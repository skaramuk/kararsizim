from django.contrib import admin

from .models import Choice, Poll, Vote


class ChoiceInline(admin.TabularInline):
    model = Choice
    min_num = 2
    max_num = 5
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "created_at")
    list_select_related = ("author",)
    search_fields = ("question", "author__username")
    inlines = [ChoiceInline]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("poll", "choice", "user", "created_at")
    list_select_related = ("poll", "choice", "user")
    readonly_fields = ("created_at",)
