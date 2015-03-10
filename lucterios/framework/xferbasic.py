# -*- coding: utf-8 -*-
'''
Created on 11 fevr. 2015

@author: sd-libre
'''

from __future__ import unicode_literals
from lxml import etree

from django.views.generic import View
from django.http import HttpResponse
from django.utils import translation, six

from lucterios.framework.tools import check_permission, raise_bad_permission, get_action_xml, menu_key_to_comp
from lucterios.framework.error import LucteriosException, get_error_trace
from django.utils.log import getLogger

class XferContainerAbstract(View):
    # pylint: disable=too-many-instance-attributes

    observer_name = ''
    extension = ""
    action = ""
    caption = ""
    closeaction = None
    icon = ""
    url_text = ""
    modal = None

    model = None
    field_id = ''

    def __init__(self, **kwargs):
        View.__init__(self, **kwargs)
        self.language = ''
        self.request = None
        self.params = {}
        self.responsesxml = etree.Element('REPONSES')
        self.responsexml = etree.SubElement(self.responsesxml, 'REPONSE')
        self.items = None
        self.item = None
        self.is_new = False
        self.has_changed = False

    def get_changed(self, caption, icon, extension=None, action=None):
        self.caption = caption
        self.icon = icon
        if extension is not None:
            self.extension = extension
        if action is not None:
            self.action = action
        return self

    def getparam(self, key):
        if key in self.params.keys():
            return self.params[key]
        else:
            return None

    def _search_model(self):
        self.has_changed = False
        if self.model is not None:
            ids = self.getparam(self.field_id)
            if ids is not None:
                ids = ids.split(';')
                if len(ids) == 1:
                    self.item = self.model.objects.get(id=ids[0])
                    self.fill_simple_fields()
                    self.fill_manytomany_fields()
                else:
                    self.items = self.model.objects.filter(id__in=ids)
            else:
                self.item = self.model()  # pylint: disable=not-callable
                self.is_new = True
                self.fill_simple_fields()

    def fill_simple_fields(self):
        field_names = self.item._meta.get_all_field_names() # pylint: disable=protected-access
        for field_name in field_names:
            dep_field = self.item._meta.get_field_by_name(field_name) # pylint: disable=protected-access
            if dep_field[2]:
                new_value = self.getparam(field_name)
                if new_value is not None:
                    if not dep_field[3]:
                        from django.db.models.fields import BooleanField
                        if isinstance(dep_field[0], BooleanField):
                            new_value = new_value != '0' and new_value != 'n'
                        setattr(self.item, field_name, new_value)
                        self.has_changed = True
        return self.has_changed

    def fill_manytomany_fields(self):
        field_names = self.item._meta.get_all_field_names() # pylint: disable=protected-access
        for field_name in field_names:
            dep_field = self.item._meta.get_field_by_name(field_name) # pylint: disable=protected-access
            if dep_field[2]:
                new_value = self.getparam(field_name)
                if new_value is not None:
                    if dep_field[3]:
                        if new_value != '':
                            relation_model = dep_field[0].rel.to
                            new_value = relation_model.objects.filter(id__in=new_value.split(';'))
                            setattr(self.item, field_name, new_value)
                            self.has_changed = True
        return self.has_changed

    def _initialize(self, request, *_, **kwargs):
        raise_bad_permission(self, request)
        _, self.extension, self.action = request.path.split('/')
        self.request = request
        for key in kwargs.keys():
            self.params[key] = kwargs[key]
        for key in request.GET.keys():
            self.params[key] = request.GET[key]
        for key in request.POST.keys():
            self.params[key] = request.POST[key]
        self.language = translation.get_language_from_request(request)
        translation.activate(self.language)

        self._search_model()

    def set_close_action(self, action, **option):
        if isinstance(action, XferContainerAbstract) and check_permission(action, self.request):
            self.closeaction = (action, option)

    def fillresponse(self):
        pass

    def _finalize(self):
        self.responsexml.attrib['observer'] = self.observer_name
        self.responsexml.attrib['source_extension'] = self.extension
        self.responsexml.attrib['source_action'] = self.action
        titlexml = etree.Element("TITLE")
        titlexml.text = self.caption.replace('_', '')
        if titlexml.text != '':
            self.responsexml.insert(0, titlexml)
        if len(self.params) > 0:
            context = etree.Element("CONTEXT")
            for key, value in self.params.items():
                new_param = etree.SubElement(context, 'PARAM')
                if isinstance(value, tuple) or isinstance(value, list):
                    new_param.text = ";".join(value)
                else:
                    new_param.text = value
                new_param.attrib['name'] = key
            self.responsexml.insert(1, context)
        if self.closeaction != None:
            etree.SubElement(self.responsexml, "CLOSE_ACTION").append(get_action_xml(self.closeaction[0], self.closeaction[1]))
        return HttpResponse(etree.tostring(self.responsesxml, xml_declaration=True, pretty_print=True, encoding='utf-8'))

    def _get_params(self):
        params = {}
        import inspect
        spec = inspect.getargspec(self.fillresponse)
        for arg_name in spec.args[1:]:
            params[arg_name] = self.getparam(arg_name)
        if isinstance(spec.args, list) and isinstance(spec.defaults, tuple):
            diff = len(spec.args) - len(spec.defaults)
            for arg_id in range(diff, len(spec.args)):
                arg_name = spec.args[arg_id]
                default_val = spec.defaults[arg_id - diff]
                if params[arg_name] is None:
                    params[arg_name] = default_val
                else:
                    if isinstance(default_val, bool):
                        params[arg_name] = (params[arg_name] != 'False') and (params[arg_name] != '0') and (params[arg_name] != '') and (params[arg_name] != 'n')
                    elif isinstance(default_val, int):
                        params[arg_name] = int(params[arg_name])
                    elif isinstance(default_val, float):
                        params[arg_name] = float(params[arg_name])
                    elif isinstance(default_val, tuple):
                        params[arg_name] = tuple(params[arg_name].split(';'))
                    elif isinstance(default_val, list):
                        params[arg_name] = params[arg_name].split(';')
        return params

    def get(self, request, *args, **kwargs):
        self._initialize(request, *args, **kwargs)
        self.fillresponse(**self._get_params())
        return self._finalize()

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

class XferContainerMenu(XferContainerAbstract):

    observer_name = 'CORE.Menu'

    def fill_menu(self, parentref, parentxml):
        from lucterios.framework.tools import MENU_LIST
        if parentref in MENU_LIST.keys():
            sub_menus = MENU_LIST[parentref]
            sub_menus.sort(key=menu_key_to_comp)  # menu_comp)
            for sub_menu_item in sub_menus:
                if check_permission(sub_menu_item[0], self.request):
                    new_xml = get_action_xml(sub_menu_item[0], {}, sub_menu_item[1], "MENU")
                    if new_xml != None:
                        parentxml.append(new_xml)
                        self.fill_menu(sub_menu_item[0].url_text, new_xml)

    def fillresponse(self):
        main_menu = etree.SubElement(self.responsexml, "MENUS")
        self.fill_menu(None, main_menu)

class XferContainerException(XferContainerAbstract):

    observer_name = 'CORE.Exception'
    exception = None

    def __init__(self):
        XferContainerAbstract.__init__(self)
        self.exception = None

    def set_except(self, exception):
        if not isinstance(exception, LucteriosException):
            getLogger(__name__).exception(exception)
        self.exception = exception

    def fillresponse(self):
        expt = etree.SubElement(self.responsexml, "EXCEPTION")
        etree.SubElement(expt, 'MESSAGE').text = six.text_type(self.exception)
        if isinstance(self.exception, LucteriosException):
            etree.SubElement(expt, 'CODE').text = six.text_type(self.exception.code)
        else:
            etree.SubElement(expt, 'CODE').text = '0'
        etree.SubElement(expt, 'DEBUG_INFO').text = get_error_trace()
        etree.SubElement(expt, 'TYPE').text = self.exception.__class__.__name__