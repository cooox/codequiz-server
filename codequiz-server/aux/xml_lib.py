# -*- coding: utf-8 -*-

import re
import xml.etree.ElementTree as ET

from IPython import embed as IPS



delim_replacements = [('<', '{+'), ('>', '+}')]
delim_replacements_rev = zip(*reversed(zip(*delim_replacements)))

pp_matches = ['<txt>.*</txt>', "<src>.*</src>"]

pp_tags = [re.findall('\<(?P<my_match>.+?)\>', m)[0] for m in pp_matches]

allowed_toplevel_tags = set(['src', 'txt', 'lelist', 'cboxlist'])


def preprocess_delimiters(xml_string):

    regex = '(?P<my_match>(?:.|\n)*?)'
    # exlpanation:
    # (?P<my_match>.*) would match any string without \n in it
    # and would return it (instead of the whole matching regex, including
    # the <txt> stuff)
    # we want \n to be included
    # (?:.|\n)* is a group that mathces every string
    # Note: (?:...) is the non capturing version of the parenthesis
    # final ? makes the * quantifier non-greedy


    pp_matches_re = [m.replace('.*', regex) for m in pp_matches]


    result_string = xml_string

    res = []
    for m in pp_matches_re:
        res += re.findall(m, xml_string)

    for old_str in res:
        new_str = old_str

        # replace the delimiters within the match
        for o, n in delim_replacements:
            new_str = new_str.replace(o, n)

        # replace the whole match
        result_string = result_string.replace(old_str, new_str)

    return result_string

def post_process_delimiters(xml_elt):
    """
    re insert the original tag-delimiters for the tmp-delimiters
    """
    if not xml_elt.tag in pp_tags:
        return # do nothing

    # these tags are not allowed to have child tags
    assert len(xml_elt) == 0
    for o, n in delim_replacements_rev:
        xml_elt.text = xml_elt.text.replace(o,n)

def test_raw_xml(xml_string):
    """
    we have certain assumtions regarding our raw_xml_strings
    -> raise an exception if an assumption is violated
    """
    if not xml_string.startswith("<?xml "):
        raise ValueError
    if not xml_string.endswith("</data>"):
        raise ValueError

    for old_d, new_d in delim_replacements:
        if new_d in xml_string:
            raise ValueError

def test_parsed_xml(root):
    """
    raise exception if assumption on xml structures are not met
    """
    tags = map(lambda e:e.tag, root)

    tag_set = set(tags)
    if not tag_set.issubset(allowed_toplevel_tags):
        raise ValueError, "invalid top level tag found"

    #!!TODO: more sanity checks (deeper level, depths)

def split_xml_root(root):
    """
    returns a list of python objects
    """

    return [TopLevelElement(child) for child in root]





class TopLevelElement(object):

    def __init__(self, elt):
        self.tag = elt.tag
        self.elt = elt
        mapping = {'txt' : self.process_txt,
                   'src' : self.process_src,
                   'lelist' : self.process_lelist,
                   'cboxlist' : self.process_cboxlist,
                   'input_list' : self.process_input_list,
                   }

        # execute the appropriate method
        mapping[self.tag]()

        #print self.elt.text
        #print "multi:", self.context.get('multiline')



    def process_txt(self):

        self.template = 'tasks/txt.html'
        self.context = {
            'text': self.elt.text,
            'multiline': "\n" in self.elt.text
            }

    def process_src(self):
        self.template = 'tasks/src.html'
        self.context = {
            'text': self.elt.text,
            'multiline': "\n" in self.elt.text
            }

    def process_lelist(self):
        elt_list, depths = zip(*[xml_to_py(xml_elt) for xml_elt in self.elt])

        self.template = 'tasks/le_list.html'
        self.context = {
            'le_list': elt_list,
        }

    def process_input_list(self):
        """
        this list can contain checkboxes, line-edits and maybe more
        """
        input_list, depths = zip(*[xml_to_py(xml_elt) for xml_elt in self.elt])

        self.template = 'tasks/part_input_list.html'
        self.context = dict(input_list = input_list)
        #IPS()

    def update_user_solution(self, sol_dict):
        """
        used to insert the user solution into the appropriate data structs
        """
        if not self.tag in ['lelist', 'cboxlist', 'input_list']:
            return

        if self.tag == 'cboxlist':
            raise NotImplementedError

        if self.tag == 'input_list':
            elt_list = self.context['input_list']
            assert len(sol_dict) == len(elt_list)

            # Challange: elt_list is ordered
            # sol_dict is not.
            # -> we construct the keys live
            for i, elt in enumerate(elt_list):
                j = i+1
                key = elt.get_type()+str(j)
#                IPS()
                sol = sol_dict[key]
                elt.user_solution = sol
                #print '>%s<:|%s|' % (repr(elt.sol.text),  repr(sol))
                elt.user_correct = \
                        (elt.sol.text == aux_convert_leadings_spaces(sol))
                if elt.user_correct:
                    elt.css_class = "sol_right"
                    elt.print_solution = "OK"
                else:
                    elt.css_class = "sol_wrong"
                    elt.print_solution = elt.sol.text

    def process_cboxlist(self):
        raise NotImplementedError



def load_xml(xml_string):
    """
    Background: We want to use html within some xml tags

    replace tag-delimiters within the right xml tags
    parse xml
    resubstitute original delimiters in the .text-attributes
    """

    if isinstance(xml_string, unicode):
        xml_string = xml_string.encode('utf8')

    test_raw_xml(xml_string)
    replaced_string = preprocess_delimiters(xml_string)

    root = ET.fromstring(replaced_string)

    for elt in root.iter():
        post_process_delimiters(elt)


    return root


class Element(object):
    """
    models an xml-Element which is not toplevel
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

        assert 'user_solution' not in self.__dict__
        assert 'print_solution' not in self.__dict__
        assert 'user_right' not in self.__dict__

        # will be overwritten later
        self.user_solution = ""
        self.print_solution = "" # will be overwritten later
        self.css_class = "undefined_css_class"

    def get_type(self):
        """
        determine which kind of elt we have (le or cbox)
        """

        if hasattr(self, 'le'):
            return 'le'
        elif hasattr(self, 'cbox'):
            return 'cbox'
        else:
#            IPS()
            raise ValueError, "unknown xml-elt-type"

    def __repr__(self):
        return 'xml:'+self.tag

def aux_convert_leadings_spaces(string):
    s2 = string.strip()
    if s2 == '':
        return s2
    idx = string.index(s2[0])

    leading_spaces = string[:idx]
    # assumes utf8 file encoding:
    brace = u"␣"#.encode('utf8')
    return string.replace(leading_spaces, brace*len(leading_spaces))


def xml_to_py(xml_elt):
    """
    converts an xml element into a py Element object
    """
    child_list = []
    depths = [-1] # if no
    for child in xml_elt:
        elt_object, depth = xml_to_py(child)
        child_list.append((child.tag, elt_object))
        depths.append(depth)

    maxdepth = max(depths)+1
    if xml_elt.text == None:
        xml_elt.text = '' # allows .strip()

    # TODO: This should live in the xml_elt
    if xml_elt.tag == "sol":
        tmp_elt_string = aux_convert_leadings_spaces(xml_elt.text)
    else:
        tmp_elt_string = xml_elt.text

    attribute_list = child_list + [( 'text', tmp_elt_string.strip() )]
    attribute_list +=  [('tag', xml_elt.tag)]
    attribute_list += xml_elt.attrib.items()
    kwargs = dict(attribute_list)
    if not len(kwargs) == len(attribute_list):
        raise ValueError, "duplicate in attribute_list. "\
        "This list should be unique: %s." % str(zip(*attribute_list)[0])

    this = Element(**kwargs)

    return this, maxdepth

if __name__ == "__main__":

    path = "task1.xml"
    with open(path, 'r') as myfile:
        content = myfile.read()

    root = load_xml(content)

    q = root.findall('lelist')[0]
    r = xml_to_py(q[0])
    IPS()

