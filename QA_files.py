import sys
import os, subprocess
import shutil
from collections import OrderedDict, defaultdict
from utils import read, regexExtraction, makeDirs, check_file, write, remove_file, added_jsonWrite, jsonRead, jsonWrite
from log import Logging
import pathlib
import re
import json
from stdScriptGen import stdScriptGen, stdScriptGenIPQC
from runScript import runScript, runIPQC
from report import ReportCheck
from lef2CellList import lef2CellList,renameAllCellBlockGDS
from verilogfile import verilogfile
from gds2cellList import pattternTop
from gds2txt import convert_gds_to_txt
LEF_CORE = []
LEF_PHANTOM = []
CDL = []
LIB = []
GDS_CORE = []
GDS_PHANTOM = []
VERILOG = []
PHANTOM_TOPCELL = "" 
CORE_TOPCELL = ""
topLayerDataType = ""
def layerExtraction(layerNumber, dataType, content):
    """
    This function will extract layer information from the given GDS txt format file.
    """
    expPattern = r"BOUNDARY(?:\s+)?\nLAYER:(?:\s+)?%s(?:\s+)?\nDATATYPE:(?:\s+)?%s(?:\s+)?\n.*(?:\s+)?\nENDEL" % (
        layerNumber, dataType)
    layerContent = regexExtraction(expPattern, content)
    if layerContent:
        coordinatesPattern = r"XY(?:/s+)?\:.*"
        for i in range(0, len(layerContent)):
            layerContent[i] = regexExtraction(
                coordinatesPattern, layerContent[i])
    return layerContent


def topBoundaryExtraction(content, fileType):
    """
    This function will extract the info for top boundary
    """
    layerDataType = [{"layerNumber": 62, "dataType": 21}, {
        "layerNumber": 0, "dataType": 0}, {"layerNumber": 212, "dataType": 121}]
    topLayerContent = []
    srefcontent = []
    ldIndex = -1
    for index, data in enumerate(layerDataType):
        topLayerContent = layerExtraction(
            data["layerNumber"], data["dataType"], content)
        if topLayerContent:

            ldIndex = index
            break
    if ldIndex > -1:
        return layerDataType[ldIndex]
    else:
        Logging.message("WARNING", "Top Boundary didn't Found on Layer (%s:%s), (%s:%s) or (%s:%s) for %s GDS"
                        % (layerDataType[0]["layerNumber"], layerDataType[0]["dataType"], layerDataType[1]["layerNumber"],
                           layerDataType[1]["dataType"], layerDataType[2]["layerNumber"], layerDataType[2]["dataType"], fileType))
        return {}


def fileCheck(TOPCELL,topCell, fileName, lib_setup_path, jsoncontent, OLD, script_settings, empty=False):
    """
    This funtion will take topCell as i/p
    """
    # fileDic = {}
    global LEF_CORE
    global LEF_PHANTOM
    global CDL
    global LIB
    global GDS_CORE
    global GDS_PHANTOM
    global VERILOG

    global topLayerDataType
    content = ""
    CORE = False
    try:
        if os.access(fileName, os.R_OK):
            content = read(fileName)
    except:
        try:
            fName = os.path.basename(fileName)
            fName = os.path.splitext(fName)
            fName = fName[0]
            convert_gds_to_txt(fileName, f".temp/.tempGds_{fName}_{topCell}.txt")
            content = read(f".temp/.tempGds_{fName}_{topCell}.txt")

            if TOPCELL is False:
                regexTopCell = "STRNAME(\s+)?:(\s+)?\"(.*)\""
                gdsCellList = pattternTop(regexTopCell, 3, content)
                jsonWrite(f".temp/.gdsCellList_{fName}_{topCell}",gdsCellList)
        except:
            pass

    # LEF
    regexLefCore = f"MACRO\s+{topCell}\n\s+CLASS"
    regexLefPhantom = f"MACRO\s+{topCell}_PA(.*)\n\s+CLASS"
    # LEF Layer Map
    regexLefLayerMap = r""
    # LIB
    #regexLib = r"timing\(\)\s+{"  # Most Probably library name will be given
    regexLib = r"timing(\s+)?\(\)\s+{"  # Most Probably library name will be given
    regexLib2 = r"library(\s+)?\("
    # regexLibIgnore = r"ccs"  # Ignoring this kind of file
    regexLibIgnore = r"\sccs\s"  # temporary
    # VERILOG
    regexVeilog = f"module\s+{topCell}(\s+)?\("
    regexVeilogPhantom = f"module\s+{topCell}_PA(.*)(\s+)?\("
    # GDS
    if TOPCELL:
        regexCoreGDS = f"STRNAME(\s+)?:(\s+)?\"{topCell}\""
        regexCoreGDSIgnore = f"SREF(\s+)?\nSNAME(\s+)?:(\s+)?\"{topCell}\"|AREF(\s+)?\nSNAME(\s+)?:(\s+)?\"{topCell}\""
        regexPhantomGDS = f"STRNAME(\s+)?:(\s+)?\"(.*)?{topCell}_PA(.*)?\""
        regexPhantomGDSIgnore = f"SREF(\s+)?\nSNAME(\s+)?:(\s+)?\"(.*)?{topCell}_PA(.*)?\"|AREF(\s+)?\nSNAME(\s+)?:(\s+)?\"(.*)?{topCell}_PA(.*)?\""
    else:
        regexCoreGDS = "STRNAME(\s+)?:.*"
    # CDL
    regexCdl = r"\.SUBCKT|\.subckt"
    regexCdlIgnore = r"\$X(\s+)?=(\s+)?\d+|\$Y(\s+)?=(\s+)?\d+"
    head_tail = os.path.split(fileName)
    if TOPCELL is False:
        regexMacroFunc= "MACRO\s+(.*)\n(\s+)?CLASS.*"
        regexPin = "PIN.*"
        regexPort = "PORT"
        if regexExtraction(regexMacroFunc, content) and regexExtraction(regexPin, content) and regexExtraction(regexPort, content):
            lef2CellList(content,lib_setup_path,topCell,head_tail,fileName,script_settings,jsoncontent,OLD)
            if not OLD:
                LEF_CORE.append(head_tail[1])

            return "LEF", fileName
        elif regexExtraction(regexLib, content) and regexExtraction(regexLib2, content):
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell,"LIB", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/LIB" % (fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old", topCell, "LIB", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/LIB" % (fileName, lib_setup_path, topCell))
            if not OLD:
                LIB.append(head_tail[1])
            return "LIB", fileName
        elif regexExtraction(regexCoreGDS, content):
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell, "GDS/Core", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/GDS/Core" %(fileName, lib_setup_path, topCell))
                os.system("ln -s %s %s/QA_checks/%s/calibre_drc" %(fileName, lib_setup_path, topCell))
                os.system("ln -s %s %s/QA_checks/%s/calibre_lvs" %(fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path,"/engr_n_old",topCell,"GDS/Core", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/GDS/Core" %
                          (fileName, lib_setup_path, topCell))
            if not OLD:
                CORE = True
                topLayerDataType = topBoundaryExtraction(content, fileName)
                GDS_CORE.append(head_tail[1])
            return "GDS", fileName
        elif regexExtraction(regexCdl, content) and not regexExtraction(regexCdlIgnore, content):
            if not check_file(os.path.join(lib_setup_path, "engr_n",topCell,"CDL", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/CDL" % (fileName, lib_setup_path,topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old",topCell,"CDL", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/CDL" %
                          (fileName, lib_setup_path,topCell))
            if not OLD:
                CDL.append(head_tail[1])
            return "CDL", fileName


    else:
        if regexExtraction(regexLefCore, content):
            if not check_file(os.path.join(lib_setup_path,"engr_n", topCell, "LEF/Core", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/LEF/Core" %
                          (fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old", topCell, "LEF/Core", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/LEF/Core" %
                          (fileName, lib_setup_path, topCell))
            if not OLD:
                LEF_CORE.append(head_tail[1])

                layer_table_content = read(os.path.join(os.path.abspath(
                    script_settings["STD_QA_SCRIPTS_DIR"]), "lefvsgds/layer_table"))
                # M(\d|\w+)
                matches = regexExtraction(r'M(\d|\w+)', layer_table_content)
                if matches and not jsoncontent["LAYER_TABLE"]:
                    for metal_txt in matches:
                        if not regexExtraction(r"LAYERs %s" % (metal_txt), content) and jsoncontent["LEF_VS_GDS_CHECK"]=="ON":
                            Logging.message(
                                "ERROR", "PLEASE ADD 'LAYER_TABLE' IN THE CONFIG")
            return "LEF", fileName
        elif regexExtraction(regexLefPhantom, content):
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell, "LEF/Phantom", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/LEF/Phantom" %
                          (fileName, lib_setup_path, topCell))

            if not check_file(os.path.join(lib_setup_path, "engr_n_old", topCell,"LEF/Phantom", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/LEF/Phantom" %
                          (fileName, lib_setup_path,topCell))
            if not OLD:
                LEF_PHANTOM.append(head_tail[1])
            return "LEF", fileName
            
        elif regexExtraction(regexLib, content) and regexExtraction(regexLib2, content) and not regexExtraction(regexLibIgnore, content):            
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell,"LIB", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/LIB" % (fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old", topCell, "LIB", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/LIB" %
                          (fileName, lib_setup_path, topCell))           
            if not OLD:
                LIB.append(head_tail[1])
            return "LIB", fileName
           
        elif regexExtraction(regexVeilog, content):           
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell, "VERILOG", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/VERILOG" %
                          (fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old", topCell,"VERILOG", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/VERILOG" %
                          (fileName, lib_setup_path, topCell))
            if not OLD:
                VERILOG.append(head_tail[1])
            return "VERILOG", fileName
            
        elif regexExtraction(regexVeilogPhantom, content):           
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell, "VERILOG", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/VERILOG" %
                          (fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old", topCell,"VERILOG", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/VERILOG" %
                          (fileName, lib_setup_path, topCell))
            if not OLD:
                VERILOG.append(head_tail[1])
            return "VERILOG", fileName
           
        elif regexExtraction(regexCoreGDS, content) and not regexExtraction(regexCoreGDSIgnore, content):
            # SrefNAMECellName = []
            # for SrefNAME in regexExtraction(regexPhantomGDSIgnore, content):
            #     SrefNAMECellName.append(SrefNAME.split("SREF\nSNAME:")[1])
            for STRNAME in regexExtraction(regexCoreGDS, content):
                STRNAMECellName = STRNAME.split("STRNAME:")[1]
                # if not STRNAMECellName in SrefNAMECellName:
                global CORE_TOPCELL
                CORE_TOPCELL = CORE_TOPCELL + STRNAMECellName.strip().lstrip('\"').rstrip('"').rstrip("/") + "\n"
                    
            if not check_file(os.path.join(lib_setup_path, "engr_n", topCell, "GDS/Core", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/GDS/Core" %
                          (fileName, lib_setup_path, topCell))
            if not check_file(os.path.join(lib_setup_path,"/engr_n_old",topCell,"GDS/Core", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/GDS/Core" %
                          (fileName, lib_setup_path, topCell))
            if not OLD:
                CORE = True
                topLayerDataType = topBoundaryExtraction(content, fileName)
                GDS_CORE.append(head_tail[1])
            return "GDS", fileName
        elif regexExtraction(regexPhantomGDS, content):
            SrefNAMECellName = []
            for SrefNAME in regexExtraction(regexPhantomGDSIgnore, content):
                SrefNAMECellName.append(SrefNAME.split("SREF\nSNAME:")[1])
            for STRNAME in regexExtraction(regexPhantomGDS, content):
                STRNAMECellName = STRNAME.split("STRNAME:")[1]
                if not STRNAMECellName in SrefNAMECellName:
                    global PHANTOM_TOPCELL
                    PHANTOM_TOPCELL = PHANTOM_TOPCELL + STRNAMECellName.strip().lstrip('\"').rstrip('"').rstrip("/") + "\n"
            if not check_file(os.path.join(lib_setup_path, "engr_n",topCell,"GDS/Phantom", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/GDS/Phantom" %
                          (fileName, lib_setup_path,topCell))

            if not check_file(os.path.join(lib_setup_path,"engr_n_old",topCell,"GDS/Phantom", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/GDS/Phantom" %
                          (fileName, lib_setup_path, topCell))
            if not OLD:
                if not CORE:
                    topLayerDataType = topBoundaryExtraction(content, fileName)
                GDS_PHANTOM.append(head_tail[1])
            return "GDS", fileName
        elif regexExtraction(regexCdl, content) and (not regexExtraction(regexCdlIgnore, content) or empty):
            if not check_file(os.path.join(lib_setup_path, "engr_n",topCell,"CDL", head_tail[1])) and not OLD:
                os.system("ln -s %s %s/engr_n/%s/CDL" % (fileName, lib_setup_path,topCell))
            if not check_file(os.path.join(lib_setup_path, "engr_n_old",topCell,"CDL", head_tail[1])) and OLD:
                os.system("ln -s %s %s/engr_n_old/%s/CDL" %
                          (fileName, lib_setup_path,topCell))
            if not OLD:
                CDL.append(head_tail[1])
            return "CDL", fileName
            
    return None, None


def check_files_notexits(TOPCELL,QA_files, libpath, TopCellName, FileList, lib_setup_path, jsoncontent, OLD, script_settings):
    Flag = False
    for file_type, file_list in QA_files.items():
        if len(file_list) == 0:
            Flag = True
           
    if Flag:
        for path, subdirs, files in os.walk(libpath):
            for file_name in files:
                if not os.path.join(path, file_name) in FileList:
                    get_filetype, get_file = fileCheck(TOPCELL,TopCellName, os.path.join(
                        path, file_name), lib_setup_path, jsoncontent, OLD, script_settings, True)
                  
                    if get_file:
                        QA_files[get_filetype].append(get_file)

    return QA_files
   
def check_extention_type(TOPCELL,path, file_name, TopCellName, lib_setup_path, jsoncontent, OLD, script_settings):
    extention_dir = {
        'LEF': ['.lef'],
        'CDL': ['.cdl', '.sp', '.spi', '.lvs'],
        'LIB': ['.lib'],
        'VERILOG': ['.v', '.mv', '.vp', '.tv'],
        'GDS': ['.gds', '.gds2', '.oas', '.gdsii']
    }
    for file_type, ext_list in extention_dir.items():
        for ext in ext_list:
            if file_name.endswith(ext):
                # read if correct file
                get_filetype, get_file = fileCheck(TOPCELL,TopCellName, os.path.join(
                    path, file_name), lib_setup_path, jsoncontent, OLD, script_settings)
                if get_file:
                    return get_filetype


def FindFiles(TOPCELL,root, TopCellName, lib_setup_path, jsoncontent, OLD, script_settings):
    Logging.message("INFO", "SEARCHING FOR FILES IN LIBRARY PATH")
    Logging.message("EXTRA", "%s" % (root))
    QA_files = {
        'LEF': [],
        'CDL': [],
        'LIB': [],
        'VERILOG': [],
        'GDS': []
    }
    FileList = []
    for path, subdirs, files in os.walk(root):
        for file_name in files:
            file_type = check_extention_type(
                TOPCELL,path, file_name, TopCellName, lib_setup_path, jsoncontent, OLD, script_settings)
            if file_type:
                FileList.append(os.path.join(path, file_name))
                QA_files[file_type].append(os.path.join(path, file_name))
    
    return QA_files, FileList


def create_library_setup(path, TopCellName,TOPCELL,jsoncontent,OLD=False):
    if not OLD:
        makeDirs(path)
        makeDirs(os.path.join(path, 'engr_n', TopCellName, 'GDS/Core'))
        makeDirs(os.path.join(path, 'engr_n', TopCellName, 'LEF/Core'))
        if TOPCELL:
            makeDirs(os.path.join(path, 'engr_n', TopCellName, 'GDS/Phantom'))
            makeDirs(os.path.join(path, 'engr_n', TopCellName, 'LEF/Phantom'))
        makeDirs(os.path.join(path, 'engr_n', TopCellName, 'CDL'))
        makeDirs(os.path.join(path, 'engr_n', TopCellName, 'LIB'))
        makeDirs(os.path.join(path, 'engr_n', TopCellName, 'VERILOG'))
        
        if jsoncontent["CALIBRE_DRC_CHECK"]=="ON": 
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'calibre_drc'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'calibre_drc'))
        if jsoncontent["CALIBRE_LVS_CHECK"]=="ON":    
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'calibre_lvs'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'calibre_lvs'))
        if jsoncontent["COMPILE_LIB_CHECK"]=="ON":            
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'compile_lib'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'compile_lib'))
        if jsoncontent["COMPILE_VERILOG_CHECK"]=="ON":    
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'compile_verilog'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'compile_verilog'))
        if jsoncontent["LEF_IN_CHECK"]=="ON":    
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'lef_in'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'lef_in'))
        if jsoncontent["LEF_VS_GDS_CHECK"]=="ON":    
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'lefvsgds'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'lefvsgds'))
        if jsoncontent["IP_TAGGING_CHECK"]=="ON":    
            makeDirs(os.path.join(path, 'QA_checks', TopCellName, 'IP_tagging'))
            os.system("chmod 777 %s"% os.path.join(path, 'QA_checks', TopCellName, 'IP_tagging'))
        if jsoncontent["IPQC_CHECK"]=="ON":    
            makeDirs(os.path.join(path, 'IPQC_checks', TopCellName))
            os.system("chmod 777 %s"% os.path.join(path, 'IPQC_checks', TopCellName))
    else:

        makeDirs(path)
        makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'GDS/Core'))
        makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'LEF/Core'))
        if TOPCELL:
            makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'GDS/Phantom'))
            makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'LEF/Phantom'))
        makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'CDL'))
        makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'LIB'))
        makeDirs(os.path.join(path, 'engr_n_old', TopCellName, 'VERILOG'))


def CreateConfigJson(content, parameter_list):
    json_dict = {}
    for param in parameter_list:
        if param == "DRC_CUSTOM_SETTINGS" or param == 'LVS_CUSTOM_SETTINGS' or param == 'LAYER_TABLE' or param == "RENAME_LAYER":
            matches = re.finditer(
                r'^(\s+)?(?!#)(\b%s\b)(.*)(?<={)((.|\n)*?(?=^}))' % param, content, re.MULTILINE)

        else:
            matches = re.finditer(r'^(\s+)?(?!#)(\b%s\b)(.*=)(.*)' % param, content, re.M)
        for matchNum, match in enumerate(matches, start=1):
            if match.group(2) == param:
                if param == "TOPCELL":
                    json_dict[param] = re.split(r"\s+",match.group(4).strip().lstrip('\"').rstrip('"').rstrip("/"))
                elif param == "RENAME_LAYER":
                    RENAME_LAYER_CONTENT=re.sub(r"^#.*", "", match.group(4).strip(), 0, re.MULTILINE)
                    json_dict[param]= RENAME_LAYER_CONTENT.split("\n")
                else:
                    json_dict[param] = match.group(4).strip().lstrip('\"').rstrip('"').rstrip("/")

    switchs = ["CALIBRE_DRC_CHECK","CALIBRE_LVS_CHECK","COMPILE_LIB_CHECK","COMPILE_VERILOG_CHECK","IP_TAGGING_CHECK","LEF_IN_CHECK","LEF_VS_GDS_CHECK","IPQC_CHECK","F_MARKER_CHECK"]
    for switch_name in switchs:
        json_dict[switch_name] = "ON"
        match = re.search(r'^(\s+)?(?!#)(\b%s\b)\s+(.*)' % switch_name, content, re.MULTILINE)
        if match:
            if match.group(3):
                json_dict[switch_name] = match.group(3).strip()

    return json_dict


def FileFoundSummary(TopCellName):
    if not len(GDS_CORE) == 0:
        Logging.message("INFO", "FOUND IP GDS FILE FOR <%s> :: TOTAL :: %s" % (TopCellName,len(GDS_CORE)))
        for FILE in GDS_CORE:
            Logging.message("EXTRA", "%s" % FILE)
    if not len(GDS_PHANTOM) == 0:
        Logging.message(
                "INFO", "FOUND PHANTOM GDS FILE FOR <%s> :: TOTAL :: %s" % (TopCellName,len(GDS_PHANTOM)))
        for FILE in GDS_PHANTOM:
            Logging.message("EXTRA", "%s" % FILE)
    if not len(LEF_PHANTOM) == 0:
        Logging.message(
                "INFO", "FOUND PHANTOM LEF FILE FOR <%s> :: TOTAL :: %s" % (TopCellName,len(LEF_PHANTOM)))
        for FILE in LEF_PHANTOM:
            Logging.message("EXTRA", "%s" % FILE)
    if not len(LEF_CORE) == 0:
        Logging.message("INFO", "FOUND IP LEF FILE for <%s> :: TOTAL :: %s" % (TopCellName,len(LEF_CORE)))
        for FILE in LEF_CORE:
            Logging.message("EXTRA", "%s" % FILE)
    if not len(LIB) == 0:
        Logging.message("INFO", "FOUND LIB FILE FOR <%s> :: TOTAL :: %s" % (TopCellName,len(LIB)))
        for FILE in LIB:
            Logging.message("EXTRA", "%s" % FILE)
    if not len(CDL) == 0:
        Logging.message("INFO", "FOUND CDL FILE FOR <%s> :: TOTAL :: %s" % (TopCellName,len(CDL)))
        for FILE in CDL:
            Logging.message("EXTRA", "%s" % FILE)
    if not len(VERILOG) == 0:
        Logging.message("INFO", "FOUND VERILOG FILE FOR <%s> :: TOTAL :: %s" %(TopCellName,len(VERILOG)))
        for FILE in VERILOG:
            Logging.message("EXTRA", "%s" % FILE)


def IPQA_file_extentions(Files,TOPCELL):
    dict = {}
    if Files["CORE_GDS"] and Files["CORE_LEF"]:
        filename, file_extension = os.path.splitext(Files["CORE_GDS"][0])
        dict["IPQC_GDS_EXTN"] = file_extension
        filename, file_extension = os.path.splitext(Files["CORE_LEF"][0])
        dict["IPQC_LEF_EXTN"] = file_extension
    elif Files["PHANTOM_GDS"] and Files["PHANTOM_LEF"]:
        filename, file_extension = os.path.splitext(Files["PHANTOM_GDS"][0])
        dict["IPQC_GDS_EXTN"] = file_extension
        filename, file_extension = os.path.splitext(Files["PHANTOM_LEF"][0])
        dict["IPQC_LEF_EXTN"] = file_extension
    
    if Files["LIB"]:
        filename, file_extension = os.path.splitext(Files["LIB"][0])

        dict["IPQC_LIB_EXTN"] = file_extension
    if Files["VERILOG"]:
        filename, file_extension = os.path.splitext(Files["VERILOG"][0])

        dict["IPQC_VER_EXTN"] = file_extension
    if Files["CDL"]:      
        filename, file_extension = os.path.splitext(Files["CDL"][0])
        dict["IPQC_CDL_EXTN"] = file_extension
    return dict
   


def extract_path_directories(jsoncontent,TOPCELL,script_settings, configpath):
  
    try:
        libpath = jsoncontent["LIBPATH"]
    except:
        Logging.message("ERROR","COULDN'T FIND THE <LIBPATH> IN THE CONFIG FILE. CHECK IF YOU PROVIDE THE CORRECT CONFIG FILE OR NOT")
    if TOPCELL:
        try:
            TopCellName = jsoncontent['TOPCELL']
        except:
            Logging.message("ERROR", "<TOPCELL> MISSING IN THE CONFIG FILE")
    else:
        if "LIBID" in jsoncontent:
            TopCellName = jsoncontent['LIBID']
        else:
            Logging.message("ERROR","<LIBID> IS MISSING IN CONFIG FILE")
    TECHNODE = ''
    FlagCopy = False
    
    path_array = libpath.split('/')
    for path_name in path_array:
        technode_match = re.search(r"(.*nm-)(.*)", path_name)
        if technode_match:
            if technode_match.group(2).strip():
                TECHNODE = technode_match.group(1)+technode_match.group(2)
                #jsoncontent["TECHNODE"] = technode_match.group(2).strip()
                #jsoncontent["TECHNODE-Marker"] = technode_match.group(2).strip()
                break

    if "TECHNODE" in jsoncontent:
        if jsoncontent["TECHNODE"]:
            jsoncontent["TECHNODE-Marker"] = jsoncontent["TECHNODE"]
        else:
            Logging.message("ERROR",f"PUT THE VALUE INSIDE <TECHNODE> IN THE CONFIG FILE\n    {configpath}")
    else:
        Logging.message("ERROR", f"<TECHNODE> IS MISSING IN THE CONFIG FILE\n    {configpath}")
    if TECHNODE: 
        try:
            lib_setup_path = libpath.split(TECHNODE)[0]
            lib_setup_path = libpath.split(lib_setup_path)[1]
            lib = pathlib.Path(lib_setup_path)
            lib_setup_path = lib.parts[:5]
            lib_setup_path = pathlib.Path(*lib.parts[:5])
            lib_setup_path = "./"+str(lib_setup_path)
            lib_setup_path_config = os.path.abspath(lib_setup_path)
            jsoncontent["LIBRARY_SETUP_PATH"] = lib_setup_path_config
        except:
            Logging.message("ERROR", f"WRONG TECHNODE IN THE CONFIG FILE\n {configpath}")
    else:
        #lib_setup_path = libpath.split(TECHNODE)[0]
        #lib_setup_path = libpath.split(lib_setup_path)[1]
        #lib = pathlib.Path(lib_setup_path)
        #lib_setup_path = lib.parts[:5]
        #lib_setup_path = pathlib.Path(*lib.parts[:5])
        lib_setup_path = "./"+str(jsoncontent["TECHNODE"])
        lib_setup_path_config = os.path.abspath(lib_setup_path)
        jsoncontent["LIBRARY_SETUP_PATH"] = lib_setup_path_config

    
    if TOPCELL:
        if check_file(lib_setup_path):
            Logging.message("WARNING","LIBRARY SETUP FILES ALREADY EXISTS. MANUALLY DELETE THE DIRECTORY")
            Logging.message("EXTRA", lib_setup_path)
            sys.exit()
        elif check_file(lib_setup_path):
            Logging.message("WARNING","LIBRARY SETUP FILES ALREADY EXISTS. MANUALLY DELETE THE DIRECTORY")
            Logging.message("EXTRA", lib_setup_path)
            sys.exit()
    else:
        if check_file(lib_setup_path+"/engr_n/"+jsoncontent["LIBID"]):
            Logging.message("WARNING","LIBRARY SETUP FILES ALREADY EXISTS. MANUALLY DELETE THE DIRECTORY")
            Logging.message("EXTRA", lib_setup_path+"/engr_n/"+jsoncontent["LIBID"])
            sys.exit()
        elif check_file(lib_setup_path+"/engr_n_old/"+jsoncontent["LIBID"]):
            Logging.message("WARNING","LIBRARY SETUP FILES ALREADY EXISTS. MANUALLY DELETE THE DIRECTORY")
            Logging.message("EXTRA", lib_setup_path+"/engr_n_old/"+jsoncontent["LIBID"])
            sys.exit()



    fixed_path_array = lib_setup_path.split('/')
    # technode/IPtype/vendor/IPname/libraryname
    vendorname=False
    libraryname=None
    current_version_number=None
    if 'VENDOR_NAME' in jsoncontent:
        if not jsoncontent["VENDOR_NAME"]=="":
            vendorname=True

    for index, path_name in enumerate(fixed_path_array):
        if index == 2:
            jsoncontent["IPQC_IP_TYPE"] = path_name
            if path_name == "NVM" or path_name == "AMS" or path_name == "MEMORY" or path_name == "CIP":
                jsoncontent["IPQC_BCHECK"] = "YES"
                jsoncontent["IPQC_BCHECK_TOOL"] = "CALIBREDRV"
            elif path_name == "LOGIC" or path_name == "IO":
                jsoncontent["IPQC_BCHECK"] = "NO"
                jsoncontent["IPQC_BCHECK_TOOL"] = ""
        if index == 3 and not vendorname:
            jsoncontent["VENDOR_NAME"] = path_name
        if index == 5:
            version_pattern_match = re.search(r"IP(\d+|.*)-(.\d+)", path_name)
            if version_pattern_match:
                if version_pattern_match.group(2):
                    version_number = version_pattern_match.group(2)
                    current_version_number = re.search(r"\d+", version_number)
                    current_version_number = current_version_number.group()
                    libraryname = path_name
            else:
                Logging.message(
                    "ERROR", "PLEASE CHECK IF THE VERSION NUMBER IS IN THIS ORDER 'IP...-<digit>'")

    previous_version_dir = ""
    if libraryname and current_version_number:
        basetail = libpath.rpartition(libraryname)
        base = basetail[0]
        versionfolder_path = os.path.abspath(base)
        dir_list = os.listdir(versionfolder_path)
        all_version_numbers = []
        for dir in dir_list:
            version_pattern_match = re.search(r"IP(\d+|.*)-(.\d+)", dir)
            if version_pattern_match:
                if version_pattern_match.group(2):
                    version_number = version_pattern_match.group(2)
                    previous_version_number = re.search(r"\d+", version_number)
                    previous_version_number = previous_version_number.group()
                    if int(previous_version_number) == (int(current_version_number) - 1):
                        previous_version_dir = dir
                        break

        if previous_version_dir:
            jsoncontent["IPQC_VERSION_OLD_DIR_PATH"] = os.path.join(
                base, previous_version_dir)
            oldlibpath = os.path.join(
                base, previous_version_dir)
            Logging.message("INFO", "FIND OLD VERSION FOR LIBRARY PATH")
            Logging.message("EXTRA", "%s" % oldlibpath)
            jsoncontent["IPQC_VERSION_OLD_DIR"] = previous_version_dir
            ########### OLD LIB ###############
            if TOPCELL:
                for index, elem in enumerate(TopCellName):
                    create_library_setup(jsoncontent["LIBRARY_SETUP_PATH"],TopCellName[index],TOPCELL,jsoncontent,OLD=True)
                    QA_files, FileList = FindFiles(
                        TOPCELL,oldlibpath, TopCellName[index], jsoncontent["LIBRARY_SETUP_PATH"], jsoncontent, True, script_settings)
                    QA_files = check_files_notexits(
                        TOPCELL, QA_files, oldlibpath, TopCellName[index], FileList, jsoncontent["LIBRARY_SETUP_PATH"], jsoncontent, True, script_settings)
                    Logging.message("INFO", "CREATED DIRECTORY AND FILES OF OLD LIBRARY SETUP <%s> TopCell" % TopCellName[index])
            else:
                create_library_setup(jsoncontent["LIBRARY_SETUP_PATH"],jsoncontent["LIBID"],TOPCELL,jsoncontent,OLD=True)
                QA_files, FileList = FindFiles(
                    TOPCELL,oldlibpath, jsoncontent["LIBID"], jsoncontent["LIBRARY_SETUP_PATH"], jsoncontent, True, script_settings)
                try:
                    lefList = jsonRead(f".temp/lefCellList_{TopCellName}_old")
                    vlogFile,verilogFileName=verilogfile(jsoncontent["LIBPATH"],lefList,lib_setup_path,TopCellName)
                    QA_files['VERILOG']= [verilogFileName]
                    VERILOG=[vlogFile]
               
                except:
                    pass

                QA_files = check_files_notexits(
                    TOPCELL, QA_files, oldlibpath, jsoncontent["LIBID"], FileList, jsoncontent["LIBRARY_SETUP_PATH"], jsoncontent, True, script_settings)
                try:
                    lefList = jsonRead(f".temp/lefCellList_{TopCellName}_old")
                    vlogFile,verilogFileName=verilogfile(jsoncontent["LIBPATH"],lefList,lib_setup_path,TopCellName)
                    QA_files['VERILOG']= [verilogFileName]
                    VERILOG=[vlogFile]
                except SystemExit:
                    sys.exit()
                except:
                    pass

                Logging.message("INFO", "CREATED DIRECTORY AND FILES OF OLD LIBRARY SETUP <%s> TopCell" % TopCellName[index])

        else:
            jsoncontent["IPQC_VERSION_OLD_DIR_PATH"] = libpath
            jsoncontent["IPQC_VERSION_OLD_DIR"] = libraryname
            FlagCopy = True

    return jsoncontent, FlagCopy


def libSetupRun(FlagCopy,lib_setup_path,jsoncontent,TOPCELL,libpath,script_settings,TopCellName,configpath,IPQC_dict):
    global LEF_CORE
    global LEF_PHANTOM
    global CDL
    global LIB
    global GDS_CORE
    global GDS_PHANTOM
    global VERILOG
    global PHANTOM_TOPCELL
    global CORE_TOPCELL
    global topLayerDataType
    LEF_CORE = []
    LEF_PHANTOM = []
    CDL = []
    LIB = []
    GDS_CORE = []
    GDS_PHANTOM = []
    VERILOG = []
    topLayerDataType = ""
    if TOPCELL is False:
        TopCellName=jsoncontent["LIBID"]
    
    create_library_setup(lib_setup_path,TopCellName,TOPCELL,jsoncontent)
    
    libpath = os.path.abspath(libpath)
    QA_files, FileList = FindFiles(
        TOPCELL,libpath, TopCellName, lib_setup_path, jsoncontent, False, script_settings)
    if TOPCELL is False:
        try:
            lefList = jsonRead(f".temp/lefCellList_{TopCellName}")
            vlogFile,verilogFileName=verilogfile(jsoncontent["LIBPATH"],lefList,lib_setup_path,TopCellName)
            QA_files['VERILOG']= [verilogFileName]
            VERILOG=[vlogFile]
       
        except:
            pass
    QA_files = check_files_notexits(
         TOPCELL,QA_files, libpath, TopCellName, FileList, lib_setup_path, jsoncontent, False, script_settings)
    if TOPCELL is False:
        try:
            lefList = jsonRead(f".temp/lefCellList_{TopCellName}")
            vlogFile,verilogFileName=verilogfile(jsoncontent["LIBPATH"],lefList,lib_setup_path,TopCellName)
            QA_files['VERILOG']= [verilogFileName]
            VERILOG=[vlogFile]
        except SystemExit:
            sys.exit()
        except:
            pass

    FileFoundSummary(TopCellName)
    if TOPCELL:
        Logging.message("INFO", "ALL FILES COPIES TO THE DIRECTORY FOR <%s> TOPCELL" % TopCellName)
    else:
        Logging.message("INFO", "ALL FILES COPIES TO THE DIRECTORY FOR <%s> LIBID" % TopCellName)
    Files = {
        "CORE_LEF": LEF_CORE,
        "PHANTOM_LEF": LEF_PHANTOM,
        "CDL": CDL,
        "LIB": LIB,
        "CORE_GDS": GDS_CORE,
        "PHANTOM_GDS": GDS_PHANTOM,
        "VERILOG": VERILOG
    }

    if FlagCopy:
        Logging.message("WARNING", "NO PREVIOUS LIBRARY EXISTS FOR <%s>" % TopCellName)
        try:
            shutil.copytree(os.path.join(jsoncontent['LIBRARY_SETUP_PATH'], "engr_n"), os.path.join(
                jsoncontent['LIBRARY_SETUP_PATH'], "engr_n_old"))
        except:
            shutil.rmtree(os.path.join(jsoncontent['LIBRARY_SETUP_PATH'], "engr_n_old"), ignore_errors=False, onerror=None) 
            shutil.copytree(os.path.join(jsoncontent['LIBRARY_SETUP_PATH'], "engr_n"), os.path.join(
                jsoncontent['LIBRARY_SETUP_PATH'], "engr_n_old"))
    # ipqc_custom = True
    # if not IPQC_dict:
    #     ipqc_custom= False
    #     IPQC_dict=IPQA_file_extentions(Files,TOPCELL)
    #     try:
    #         IPQC_dict["IPQC_BOUNDARY_LAYER"] = str(topLayerDataType["layerNumber"])
    #         IPQC_dict["IPQC_BOUNDARY_DATATYPE"] = str(topLayerDataType["dataType"])
    #     except:
    #         if TOPCELL:
    #             Logging.message("WARNING",f"IPQC_BOUNDARY_LAYER AND IPQC_BOUNDARY_DATATYPE NOT FOUND. MAY BE INVALID <{TopCellName}> TOPCELL GIVEN IN THE CONFIG <{configpath}>")
    #         else:
    #             Logging.message("WARNING",f"INVALID <{TopCellName}> LIBID GIVEN IN THE CONFIG <{configpath}>")
    
    ipqc_extn=IPQA_file_extentions(Files,TOPCELL)
    for key, value in ipqc_extn.items():
        if key in IPQC_dict:
            if IPQC_dict[key].strip()=="":
                IPQC_dict[key]=value
        else:
            IPQC_dict[key]=value

    if "IPQC_BOUNDARY_LAYER" in IPQC_dict:
        if IPQC_dict["IPQC_BOUNDARY_LAYER"].strip()=="":
            try:
                IPQC_dict["IPQC_BOUNDARY_LAYER"] = str(topLayerDataType["layerNumber"])
            except:
                Logging.message("WARNING",f"IPQC_BOUNDARY_LAYER NOT FOUND. MAY BE INVALID <{TopCellName}> TOPCELL GIVEN IN THE CONFIG <{configpath}>")
    else:
        try:
            IPQC_dict["IPQC_BOUNDARY_LAYER"] = str(topLayerDataType["layerNumber"])
        except:
            Logging.message("WARNING",f"IPQC_BOUNDARY_LAYER NOT FOUND. MAY BE INVALID <{TopCellName}> TOPCELL GIVEN IN THE CONFIG <{configpath}>")
    
    if "IPQC_BOUNDARY_DATATYPE" in IPQC_dict:
        if IPQC_dict["IPQC_BOUNDARY_DATATYPE"].strip()=="":
            try:
                IPQC_dict["IPQC_BOUNDARY_DATATYPE"] = str(topLayerDataType["dataType"])
            except:
                Logging.message("WARNING",f"IPQC_BOUNDARY_DATATYPE NOT FOUND. MAY BE INVALID <{TopCellName}> TOPCELL GIVEN IN THE CONFIG <{configpath}>")
    else:
        try:
            IPQC_dict["IPQC_BOUNDARY_DATATYPE"] = str(topLayerDataType["dataType"])
        except:
            Logging.message("WARNING",f"IPQC_BOUNDARY_DATATYPE NOT FOUND. MAY BE INVALID <{TopCellName}> TOPCELL GIVEN IN THE CONFIG <{configpath}>")    
        
    #F-MARKER
   
    if Files['CORE_GDS']:
        IPQC_dict["CORE_GDS_PATH"] = os.path.join(lib_setup_path, 'engr_n',TopCellName,'GDS/CORE' , Files['CORE_GDS'][0])
    else:
        IPQC_dict["CORE_GDS_PATH"] = ""
    if TOPCELL:
        if not Files['CORE_GDS'] and not Files['PHANTOM_GDS'] and jsoncontent["CALIBRE_DRC_CHECK"]=="ON" and jsoncontent["CALIBRE_LVS_CHECK"]=="ON" and jsoncontent["IP_TAGGING_CHECK"]=="ON" and jsoncontent["LEF_VS_GDS_CHECK"]=="ON":
            Logging.message("ERROR", "MISSNG BOTH CORE AND PHANTOM GDS FOR %s" % TopCellName)
        
        if Files['PHANTOM_GDS']:
            IPQC_dict["PHANTOM_GDS_PATH"] = os.path.join(lib_setup_path,'engr_n', TopCellName,'GDS/PHANTOM',Files['PHANTOM_GDS'][0])
        else:
            IPQC_dict["PHANTOM_GDS_PATH"] = ""
        
        IPQC_dict["PHANTOM_TOPCELL"] = PHANTOM_TOPCELL
        IPQC_dict["CORE_TOPCELL"] = CORE_TOPCELL
        
        # delete the custom parameters if empty
        # for ipqc_param in ["IPQC_IP_TYPE", "IPQC_BCHECK", "IPQC_BCHECK_TOOL"]:
        for ipqc_param in ['IPQC_IP_TYPE', 'IPQC_BCHECK', 'IPQC_BCHECK_TOOL', 'IPQC_GDS_EXTN', 'IPQC_LEF_EXTN', 'IPQC_LIB_EXTN', 'IPQC_VER_EXTN', 'IPQC_CDL_EXTN', 'IPQC_BOUNDARY_LAYER', 'IPQC_BOUNDARY_DATATYPE']:
            if ipqc_param in IPQC_dict:
                if IPQC_dict[ipqc_param].strip()=="":
                    del IPQC_dict[ipqc_param]
                            
        added_jsonWrite(".temp/config.json", IPQC_dict)
        jsoncontent = jsonRead(".temp/config")
    else:
       
        if not Files['CORE_GDS']:
            Logging.message("ERROR", "MISSING CORE FOR %s" % TopCellName)
        added_jsonWrite(f".temp/{TopCellName}_config.json", IPQC_dict)
        jsoncontent = jsonRead(f".temp/{TopCellName}_config")
    stdScriptGen(TOPCELL,Files,jsoncontent,script_settings, TopCellName)
    if TOPCELL is False:
         renameAllCellBlockGDS(jsoncontent,lib_setup_path,TopCellName,Files)
    runScript(lib_setup_path, Files,script_settings,TopCellName,TOPCELL)
    extn=ReportCheck(lib_setup_path,jsoncontent,TopCellName)

    stdScriptGenIPQC(extn,Files,jsoncontent,script_settings, TopCellName,TOPCELL)
    runIPQC(lib_setup_path, Files,script_settings,TopCellName,TOPCELL)


def AutoQAMain(script_settings,configpath,TOPCELL):
    
    if not check_file(os.path.abspath(configpath)):
        Logging.message("ERROR", "<%s> CONFIG FILE IS MISSING"%configpath)
    Logging.message("INFO", "READING <%s> CONFIG FILE" %configpath)
    content = read(os.path.abspath(configpath))
    parameter_list = ['ALL_CELLS_BLOCK','PATTERNPATH','LIBID', 'LIBPATH', 'TOPCELL',  'TECHDIR_LVS', 'TECHDIR_DRC', 'EXCEL_PATH',
                      'DRC_CUSTOM_SETTINGS', 'LVS_CUSTOM_SETTINGS', 'TECH', 'TECH_PATH', 'LAYER_TABLE','TECHNODE', 'VENDOR_NAME','IPQC_CUSTOM_CONFIG_PATH', 'RENAME_LAYER']
        
    jsoncontentdict = CreateConfigJson(content, parameter_list)
    #print(jsoncontentdict)

    IPQC_dict={}

    ipqc_parameter_list=['IPQC_IP_TYPE', 'IPQC_BCHECK', 'IPQC_BCHECK_TOOL', 'IPQC_GDS_EXTN', 'IPQC_LEF_EXTN', 'IPQC_LIB_EXTN', 'IPQC_VER_EXTN', 'IPQC_CDL_EXTN', 'IPQC_BOUNDARY_LAYER', 'IPQC_BOUNDARY_DATATYPE']        
    IPQC_dict = CreateConfigJson(content, ipqc_parameter_list)
    
    json_dict, FlagCopy = extract_path_directories(jsoncontentdict,TOPCELL,script_settings, configpath)
    json_content = json.dumps(json_dict, indent=4)
    # if TOPCELL:
    #     write('.temp/config.json', json_content, False)
    #     try:
    #         f = open('.temp/config.json')
    #     except:
    #         Logging.message("ERROR", "COULDN'T READ THE <.temp/config.json> file")
    #     jsoncontent = json.load(f)
    #     parameter_list_imp = ['LIBPATH', 'TOPCELL','TECHNODE']
    #     if jsoncontent["LEF_IN_CHECK"]=="ON":
    #         parameter_list_imp.append("TECH")
    #         parameter_list_imp.append("TECH_PATH")

    # else:
    #     write('.temp/'+jsoncontentdict["LIBID"]+'_config.json', json_content, False)
    #     try:
    #         f = open('.temp/'+jsoncontentdict["LIBID"]+'_config.json')
    #     except:
    #         Logging.message("ERROR", "COULDN'T READ THE <%s> file"%('.temp/'+jsoncontentdict["LIBID"]+'_config.json'))
    #     jsoncontent = json.load(f)
    #     parameter_list_imp = ['ALL_CELLS_BLOCK','LIBID','LIBPATH','TECHDIR_LVS', 'TECHDIR_DRC',
    #                      'TECH', 'TECH_PATH','TECHNODE']


    # for key in parameter_list_imp:
    #     if key in jsoncontent:
    #         if jsoncontent[key] == "" or  jsoncontent[key][0]=="":
    #             Logging.message("ERROR","MISSING <%s> PARAMETER VALUE IN <%s> CONFIG FILE" % (key,configpath))
    #     else:
    #         Logging.message("ERROR","MISSING <%s> PARAMETER IN <%s> CONFIG FILE" % (key,configpath))

    # libpath = jsoncontent['LIBPATH']
    # try:
    #     TopCellName = jsoncontent['TOPCELL']
    # except:
    #     pass
    # TECHNODE = jsoncontent['TECHNODE']
    # if not check_file(os.path.abspath(libpath)):
    #     Logging.message("ERROR", "INVALID <%s> LIBRARY PATH IN <%s> CONFIG FILE" % (libpath,configpath))

    # lib_setup_path = jsoncontent["LIBRARY_SETUP_PATH"]
    

    # Logging.message("INFO", "CREATING DIRECTORY OF LIBRARY SETUP FOR <%s> CONFIG FILE"%configpath)
    # global LEF_CORE
    # global LEF_PHANTOM
    # global CDL
    # global LIB
    # global GDS_CORE
    # global GDS_PHANTOM
    # global VERILOG
    # global PHANTOM_TOPCELL
    # global CORE_TOPCELL
    # global topLayerDataType
    # if TOPCELL is False:
    #     libSetupRun(FlagCopy,lib_setup_path,jsoncontent,TOPCELL,libpath,script_settings,"",configpath,IPQC_dict)
    # else:
    #     for index, elem in enumerate(TopCellName):
    #         libSetupRun(FlagCopy,lib_setup_path,jsoncontent,TOPCELL,libpath,script_settings,TopCellName[index],configpath,IPQC_dict)
            
