# -*- coding: utf-8 -*-
'''
Created on march 2015

@author: sd-libre
'''

from __future__ import unicode_literals
import re

from django.db import models
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.utils import six, formats

def get_value_converted(value, bool_textual=False):
    # pylint: disable=too-many-return-statements, too-many-branches
    import datetime
    if hasattr(value, 'all'):
        values = []
        for val_item in value.all():
            values.append(six.text_type(val_item))
        return "{[br/]}".join(values)
    elif isinstance(value, datetime.datetime):
        return formats.date_format(value, "DATETIME_FORMAT")
    elif isinstance(value, datetime.date):
        return formats.date_format(value, "DATE_FORMAT")
    elif isinstance(value, datetime.time):
        return formats.date_format(value, "TIME_FORMAT")
    elif isinstance(value, bool):
        if bool_textual:
            if value:
                return _("Yes")
            else:
                return _("No")
        else:
            if value:
                return six.text_type("1")
            else:
                return six.text_type("0")
    elif value is None:
        return six.text_type("---")
    else:
        return value

def get_value_if_choices(value, dep_field):
    if hasattr(dep_field[0], 'choices') and (dep_field[0].choices is not None) and (len(dep_field[0].choices) > 0):
        for choices_key, choices_value in dep_field[0].choices:
            if choices_key == value:
                value = six.text_type(choices_value)
                break
    return value

class LucteriosModel(models.Model):

    TO_EVAL_FIELD = re.compile("#[a-z_0-9]+")

    default_fields = []

    @classmethod
    def get_long_name(cls):
        instance = cls()
        return "%s.%s" % (instance._meta.app_label, instance._meta.object_name)  # pylint: disable=no-member,protected-access

    def evaluate(self, text):
        value = text
        for field in self.TO_EVAL_FIELD.findall(text):
            field_val = get_value_converted(getattr(self, field[1:]), True)
            value = value.replace(field, six.text_type(field_val))
        return value

    @classmethod
    def _get_list_fields_names(cls, current_desc, readonly):
        res = []
        for fieldname in current_desc:
            if fieldname is None:
                for subclass in cls.__bases__:
                    if issubclass(subclass, LucteriosModel):
                        res.extend(subclass.get_fields_names(readonly))
            else:
                res.append(fieldname)
        return res

    @classmethod
    def get_fields_names(cls, readonly):
        res = None
        if readonly:
            dataname = cls.__name__.lower() + '__showfields'
        else:
            dataname = cls.__name__.lower() + '__editfields'
        if hasattr(cls, dataname):
            current_desc = getattr(cls, dataname)
            if isinstance(current_desc, list):
                res = cls._get_list_fields_names(current_desc, readonly)
            elif isinstance(current_desc, dict):
                res = {}
                for (key, value) in current_desc.items():
                    res[key] = cls._get_list_fields_names(value, readonly)
        return res

    @classmethod
    def _get_list_fields_for_search(cls, current_desc):
        res = []
        for fieldname in current_desc:
            if fieldname is None:
                for subclass in cls.__bases__:
                    if issubclass(subclass, LucteriosModel):
                        res.extend(subclass.get_fieldnames_for_search())
            else:
                res.append(fieldname)
        return res

    @classmethod
    def get_print_fields(cls):
        from django.db.models.fields.related import ForeignKey        
        fields = []
        item = cls()
        if hasattr(cls, "print_fields"):
            dataname = "print_fields"
        else:            
            dataname = "default_fields"
        for field_name in getattr(cls, dataname):
            if field_name[-4:] == '_set':
                child = getattr(item, field_name)
                print(child.__module__)
                field_title = child.model._meta.verbose_name
                for sub_title, sub_name in child.model.get_print_fields():
                    fields.append(("%s > %s" % (field_title, sub_title), "%s__%s" % (field_name, sub_name)))
            else:
                dep_field = item._meta.get_field_by_name(field_name)
                field_title = dep_field[0].verbose_name
                if dep_field[2] and not dep_field[3] and not isinstance(dep_field[0], ForeignKey): 
                    fields.append((field_title, field_name))
                else:
                    for sub_title, sub_name in dep_field[0].rel.to.get_print_fields():
                        fields.append(("%s > %s" % (field_title, sub_title), "%s.%s" % (field_name, sub_name)))
        return fields

    @classmethod
    def get_fieldnames_for_search(cls):
        res = []
        dataname = cls.__name__.lower() + '__searchfields'
        if hasattr(cls, dataname):
            current_desc = getattr(cls, dataname)
            if isinstance(current_desc, list):
                res = cls._get_list_fields_for_search(current_desc)
        return res

    def can_delete(self):
        # pylint: disable=unused-argument,no-self-use
        return ''

    def edit(self, xfer):
        # pylint: disable=unused-argument,no-self-use
        return

    def show(self, xfer):
        # pylint: disable=unused-argument,no-self-use
        return

    def saving(self, xfer):
        # pylint: disable=unused-argument,no-self-use
        return

    class Meta(object):
        # pylint: disable=no-init
        abstract = True

class LucteriosSession(Session, LucteriosModel):

    default_fields = [(_('username'), 'username'), 'expire_date']

    @property
    def username(self):
        data = self.get_decoded()
        user_id = data.get('_auth_user_id', None)
        if user_id is None:
            return "---"
        else:
            return User.objects.get(id=user_id).username  # pylint: disable=no-member

    class Meta(object):
        # pylint: disable=no-init
        proxy = True
        default_permissions = []
        verbose_name = _('session')
        verbose_name_plural = _('sessions')
