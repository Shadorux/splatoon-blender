bl_info = {
    "name": "Splatoon Tools",
    "author": "Shadorux",
    "version": (2, 0, 1),
    "blender": (5, 2, 0),
    "location": "View3D > Add > Mesh > Inkling",
    "description": "Create a procedural Splatoon character in few clicks.",
    "warning": "",
    "doc_url": "",
    "category": "Add Mesh",
}

import bpy
import os
from types import SimpleNamespace
import bmesh
from bpy.types import Operator, Panel
from bpy.props import FloatVectorProperty
from bpy_extras.object_utils import AddObjectHelper, object_data_add
from mathutils import Vector
from bpy_extras.object_utils import AddObjectHelper
from pathlib import Path
from . import cloth_import, weapon_import, item_import, fast_squid, fast_octopus

# Resolve bundled scripts and .blend assets relative to this add-on instead of
# assuming Blender installed it in a folder literally named "Splatoon Tools".
srcPath = Path(__file__).resolve().parent

def deselect_all_objects():
    for obj in bpy.context.view_layer.objects:
        if obj is not None:
            obj.select_set(False)


_GEAR_PREFIXES = ("Clt_", "Shs_", "Wmn_", "Head_", "Item_")


def _is_gear_object(obj):
    """Keep imported clothing, shoes and weapons when replacing a player."""
    return obj.name.startswith(_GEAR_PREFIXES)


def remove_existing_player(scene):
    """Remove the generated player owned by the persistent sidebar.

    The original operator leaves every linked body and hair object in the
    scene.  This uses a scene pointer for new files and a name/constraint
    fallback for files made by older versions, while leaving imported gear
    objects (Clt_, Shs_, Wmn_) alone.
    """
    old_armature = getattr(scene, "splatoon_player_armature", None)
    if old_armature is None or old_armature.name not in bpy.data.objects:
        old_armature = None
        wanted = str(getattr(scene, "splatoon_name", "Inkling"))
        candidates = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
        named = [obj for obj in candidates if obj.name == wanted or obj.name.startswith(wanted + ".")]
        tagged = [obj for obj in candidates if obj.get("splatoon_generated")]
        if named:
            old_armature = sorted(named, key=lambda obj: obj.name)[-1]
        elif tagged:
            old_armature = tagged[-1]

    if old_armature is None:
        return

    to_remove = set()

    def collect_children(obj):
        for child in list(obj.children):
            if _is_gear_object(child):
                continue
            to_remove.add(child)
            collect_children(child)

    to_remove.add(old_armature)
    collect_children(old_armature)

    # Hair armatures are constrained to the body but are not parented to it.
    for obj in list(bpy.data.objects):
        if obj in to_remove or obj.type != 'ARMATURE':
            continue
        owns_old = obj.get("splatoon_owner") == old_armature.name
        constrained = any(
            getattr(con, "target", None) == old_armature
            for bone in obj.pose.bones
            for con in bone.constraints
        )
        if owns_old or constrained or obj.name.startswith("Hair "):
            if owns_old or constrained:
                to_remove.add(obj)
                collect_children(obj)

    for obj in list(to_remove):
        if obj.name in bpy.data.objects and not _is_gear_object(obj):
            bpy.data.objects.remove(obj, do_unlink=True)
    if hasattr(scene, "splatoon_player_armature"):
        scene.splatoon_player_armature = None

def path_iterator(folder_path):
    for fp in os.listdir(folder_path):
        if fp.endswith( tuple( bpy.path.extensions_image ) ):
            yield fp

def import_weapon(armature=None, path="", file="", inkA=(0,0,0)):
    deselect_all_objects()
    
    bpy.ops.import_scene.fbx(filepath = path+file)
    
    obj = bpy.context.view_layer.objects.active
    
    # TRANSFORMING
    obj.scale = (1,1,1)
    
    #RIGING
    for child in obj.children:
        deselect_all_objects()
        bpy.context.view_layer.objects.active = child
        
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.remove_doubles(threshold=0.001, use_unselected=True, use_sharp_edge_from_normals=True)
        bpy.ops.object.editmode_toggle()
        
        deselect_all_objects()
        child.select_set(True)
        bpy.context.view_layer.objects.active = child
        
        # SHADING
        
        nodes = bpy.context.active_object.active_material.node_tree.nodes
        links = bpy.context.active_object.active_material.node_tree.links
        
        for node in nodes:
            nodes.remove(node)
        
        output = nodes.new(type="ShaderNodeOutputMaterial")
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        links.new(bsdf.outputs[0], output.inputs[0])

        mix_node = None
        alb_node = None
        inka_color = (inkA[0], inkA[1], inkA[2], 1)
        
        for img_path in path_iterator( path ):
            if img_path.lower().startswith(bpy.context.active_object.active_material.name.lower()+"_"):
                full_path = os.path.join( path, img_path )
                
                img_node = nodes.new(type="ShaderNodeTexImage")
                img_node.image = bpy.data.images.load(full_path, check_existing=True)
            
                if img_path.endswith("tcl.png"):
                    mix_node = nodes.new(type="ShaderNodeMix")
                    mix_node.data_type = "RGBA"
                    
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    
                    links.new(img_node.outputs[0], mix_node.inputs[0])
                    
                    if alb_node != None:
                        links.new(mix_node.outputs[0], bsdf.inputs[0])
                        links.new(alb_node.outputs[0], mix_node.inputs[6])
                        mix_node.inputs[6].default_value = inka_color
                
                if img_path.endswith("alb.png"):
                    alb_node = img_node
                    links.new(img_node.outputs[0], bsdf.inputs[0])
                    
                    if mix_node != None:
                        links.new(mix_node.outputs[0], bsdf.inputs[0])
                        links.new(img_node.outputs[0], mix_node.inputs[6])
                        mix_node.inputs[6].default_value = inka_color
                            
                if img_path.endswith("mtl.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[6])
                            
                if img_path.endswith("spc.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[7])
                            
                if img_path.endswith("rgh.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[9])
                            
                if img_path.endswith("emm.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[20])
                                
                if img_path.endswith("opa.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[21])
                    
                if img_path.endswith("alp.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[21])
            
                if img_path.endswith("nrm.png"):
                    nrm_node = nodes.new("ShaderNodeNormalMap")
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(nrm_node.outputs[0], bsdf.inputs[22])
                    links.new(img_node.outputs[0], nrm_node.inputs[1])
    
    if not bsdf.inputs[0].links:
        bsdf.inputs[0].default_value = inka_color
    
    deselect_all_objects()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def import_clt(armature=None, path="", file="", inkA=(0,0,0)):
    deselect_all_objects()
    
    bpy.ops.import_scene.fbx(filepath = path+file)
    
    obj = bpy.context.view_layer.objects.active
    
    # TRANSFORMING
    bpy.ops.transform.resize(value=(4.85 * armature.scale.x, 4.85 * armature.scale.y, 4.85 * armature.scale.z))
    bpy.ops.rotation_euler = armature.rotation_euler
    bpy.ops.transform.translate(value=(0, 0.82 * armature.scale.y, 0), orient_type='LOCAL')
    
    #RIGING
    for child in obj.children:
        deselect_all_objects()
        child.select_set(True)
        
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        
        bpy.ops.object.parent_set(type='ARMATURE')
        
        deselect_all_objects()
        child.select_set(True)
        bpy.context.view_layer.objects.active = child

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.remove_doubles(threshold=0.001, use_unselected=True, use_sharp_edge_from_normals=True)
        bpy.ops.object.editmode_toggle()
        
        bpy.ops.object.modifier_add(type='VERTEX_WEIGHT_MIX')
        bpy.context.object.modifiers[2].mix_set = 'ALL'
        bpy.context.object.modifiers[2].mix_mode = 'ADD'
        bpy.context.object.modifiers[2].vertex_group_a = "arm1_L"
        bpy.context.object.modifiers[2].vertex_group_b = "arm1sub_L"
        if bpy.context.object.modifiers["VertexWeightMix"].is_active == False:
            bpy.ops.object.modifier_apply(modifier="VertexWeightMix", report=True)
        else:
            bpy.ops.object.modifier_remove(modifier="VertexWeightMix", report=True)
        
        bpy.ops.object.modifier_add(type='VERTEX_WEIGHT_MIX')
        bpy.context.object.modifiers[2].mix_set = 'ALL'
        bpy.context.object.modifiers[2].mix_mode = 'ADD'
        bpy.context.object.modifiers[2].vertex_group_a = "arm1_R"
        bpy.context.object.modifiers[2].vertex_group_b = "arm1sub_R"
        if bpy.context.object.modifiers["VertexWeightMix"].is_active == False:
            bpy.ops.object.modifier_apply(modifier="VertexWeightMix", report=True)
        else:
            bpy.ops.object.modifier_remove(modifier="VertexWeightMix", report=True)
        
        bpy.ops.object.modifier_add(type='VERTEX_WEIGHT_MIX')
        bpy.context.object.modifiers[2].mix_set = 'ALL'
        bpy.context.object.modifiers[2].mix_mode = 'ADD'
        bpy.context.object.modifiers[2].vertex_group_a = "crotch_L"
        bpy.context.object.modifiers[2].vertex_group_b = "leg1_L"
        if bpy.context.object.modifiers["VertexWeightMix"].is_active == False:
            bpy.ops.object.modifier_apply(modifier="VertexWeightMix", report=True)
        else:
            bpy.ops.object.modifier_remove(modifier="VertexWeightMix", report=True)
        
        bpy.ops.object.modifier_add(type='VERTEX_WEIGHT_MIX')
        bpy.context.object.modifiers[2].mix_set = 'ALL'
        bpy.context.object.modifiers[2].mix_mode = 'ADD'
        bpy.context.object.modifiers[2].vertex_group_a = "crotch_R"
        bpy.context.object.modifiers[2].vertex_group_b = "leg1_R"
        if bpy.context.object.modifiers["VertexWeightMix"].is_active == False:
            bpy.ops.object.modifier_apply(modifier="VertexWeightMix", report=True)
        else:
            bpy.ops.object.modifier_remove(modifier="VertexWeightMix", report=True)

        
        name_list = [
            ['joint_root','Spawner_Root'],
            ['hip','Waist'],
            ['spine1','Spine_1'],
            ['spine2','Spine_2'],
            ['chest','Spine_3'],
            ['shoulder_L','Clavicle_L'],
            ['arm1_L','Arm_1_L'],
            ['arm2_L','Arm_2_L'],
            ['hand_L','Wrist_L'],
            ['shoulder_R','Clavicle_R'],
            ['arm1_R','Arm_1_R'],
            ['arm2_R','Arm_2_R'],
            ['hand_R','Wrist_R'],
            ['head','Head'],
            ['leg1_L','Leg_1_L'],
            ['leg1_R','Leg_1_R'],
        ]

        v_groups = child.vertex_groups
        for n in name_list:
            if n[0] in v_groups:
                if v_groups[n[0]] != None:
                    v_groups[n[0]].name = n[1]
        
        
        deselect_all_objects()
        child.select_set(True)
        bpy.context.view_layer.objects.active = child
                    
        bpy.ops.object.modifier_remove(modifier="Armature", report=True)
        
        # SHADING
        
        nodes = bpy.context.active_object.active_material.node_tree.nodes
        links = bpy.context.active_object.active_material.node_tree.links
        
        for node in nodes:
            nodes.remove(node)
        
        output = nodes.new(type="ShaderNodeOutputMaterial")
        bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
        links.new(bsdf.outputs[0], output.inputs[0])
        
        alb_node = None
        mix_node = None
        
        for img_path in path_iterator( path ):
            if img_path.lower().startswith(bpy.context.active_object.active_material.name.lower()+"_"):
                full_path = os.path.join( path, img_path )
                
                img_node = nodes.new(type="ShaderNodeTexImage")
                img_node.image = bpy.data.images.load(full_path, check_existing=True)
            
                if img_path.endswith("tcl.png"):
                    mix_node = nodes.new(type="ShaderNodeMix")
                    mix_node.data_type = "RGBA"
                    
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    
                    links.new(img_node.outputs[0], mix_node.inputs[0])
                    
                    if alb_node != None:
                        links.new(mix_node.outputs[0], bsdf.inputs[0])
                        links.new(alb_node.outputs[0], mix_node.inputs[6])
                
                if img_path.endswith("alb.png"):
                    alb_node = img_node
                    links.new(img_node.outputs[0], bsdf.inputs[0])
                    
                    if mix_node != None:
                        links.new(mix_node.outputs[0], bsdf.inputs[0])
                        links.new(img_node.outputs[0], mix_node.inputs[6])
                            
                if img_path.endswith("mtl.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[6])
                            
                if img_path.endswith("spc.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[7])
                            
                if img_path.endswith("rgh.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[9])
                            
                if img_path.endswith("emm.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[20])
                                
                if img_path.endswith("opa.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[21])
                    
                if img_path.endswith("alp.png"):
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(img_node.outputs[0], bsdf.inputs[21])
            
                if img_path.endswith("nrm.png"):
                    nrm_node = nodes.new("ShaderNodeNormalMap")
                    img_node.image.colorspace_settings.name = 'Non-Color'
                    links.new(nrm_node.outputs[0], bsdf.inputs[22])
                    links.new(img_node.outputs[0], nrm_node.inputs[1])
    
    
    deselect_all_objects()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)
    

# HAIR
def create_hair(index=0, armature=None, self=None, type="inkling_F"):
    
    hair_armature = None
    mesh = None
    
    deselect_all_objects()
    src_path=str(srcPath) + "/" + type + "_hair.blend"
 
    with bpy.data.libraries.load(src_path) as (data_from, data_to):
        available = sorted({
            int(name.split()[1].split('_')[0])
            for name in data_from.objects
            if name.startswith("Hair ") and name.split()[1].split('_')[0].isdigit()
        })
        if not available:
            return
        if index not in available:
            # Octoling assets currently contain indices 0-7, while Inkling
            # assets contain 0-15.  Clamp old/global UI values safely.
            index = min(available, key=lambda value: abs(value - index))
        data_to.objects = data_from.objects
 
    for obj in data_to.objects:
        if obj.name.startswith("Hair "+"{:02d}".format(index)):
            bpy.context.collection.objects.link(obj)
            obj["splatoon_generated"] = True
            obj["splatoon_owner"] = armature.name
            if obj.type == "ARMATURE":
                hair_armature = obj
            else:
                mesh = obj
    
    if hair_armature is None or mesh is None:
        if armature is not None:
            deselect_all_objects()
            armature.select_set(True)
            bpy.context.view_layer.objects.active = armature
        return

    deselect_all_objects()
    hair_armature.select_set(True)
    bpy.context.view_layer.objects.active = hair_armature

    bpy.ops.object.posemode_toggle()
    bpy.context.object.pose.bones["Head_Root"].constraints["Copy Transforms"].target = bpy.data.objects[armature.name]
    bpy.context.object.pose.bones["Head_Root"].constraints["Copy Transforms"].subtarget = "Head"
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.object.pose.bones["Head_Root"].constraints.new(type='COPY_SCALE')
    bpy.context.object.pose.bones["Head_Root"].constraints["Copy Scale"].target = bpy.data.objects[armature.name]
    bpy.context.object.pose.bones["Head_Root"].constraints["Copy Scale"].subtarget = "Hair_Scale"
    
    # MATERIALS
    inka_color = (self.ink_A[0], self.ink_A[1], self.ink_A[2], 1)
    inkb_color = (self.ink_B[0], self.ink_B[1], self.ink_B[2], 1)
    
    mesh.active_material = mesh.active_material.copy()
    hair_mat = mesh.active_material
    
    hair_mat.node_tree.nodes["Group"].inputs[0].default_value = inka_color
    hair_mat.node_tree.nodes["Group"].inputs[2].default_value = inkb_color
    hair_mat.node_tree.nodes["Group"].inputs[4].default_value = self.hair_emission
    
    deselect_all_objects()
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    
# EYEBLOW
def create_eyeblow(index=0, armature=None, self=None, type="inkling_F"):

    mesh = None
    
    deselect_all_objects()
    src_path=str(srcPath) + "/"+type+"_eyeblow.blend"
 
    with bpy.data.libraries.load(src_path) as (data_from, data_to):
        data_to.objects = data_from.objects
 
    for obj in data_to.objects:
        if obj.name.lower().startswith("eyeblow "+str(index)):
            bpy.context.collection.objects.link(obj)
            obj["splatoon_generated"] = True
            obj["splatoon_owner"] = armature.name
            mesh = obj

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    mesh.select_set(True)

    bpy.ops.object.parent_set(type='ARMATURE')

    # MATERIALS
    inka_color = (self.ink_A[0], self.ink_A[1], self.ink_A[2], 1)
    inkb_color = (self.ink_B[0], self.ink_B[1], self.ink_B[2], 1)
    
    mesh.active_material = mesh.active_material.copy()
    eyeblow_mat = mesh.active_material
    eyeblow_mat.node_tree.nodes[1].inputs[0].default_value = inka_color
    eyeblow_mat.node_tree.nodes[1].inputs[1].default_value = inkb_color
    
    mesh.select_set(False)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    
def create_bottom(index=0, armature=None, self=None):
    deselect_all_objects()
    
    maskIndex = ["00","06","05","02","05","07","08","07","00"]
    
    bpy.ops.object.mode_set(mode='OBJECT'),

    mesh = None
    
    deselect_all_objects()
    src_path=str(srcPath) + "/bottom_F.blend"
 
    with bpy.data.libraries.load(src_path) as (data_from, data_to):
        data_to.objects = data_from.objects
 
    for obj in data_to.objects:
        if obj.name.startswith("Bottom "+str(index)):
            bpy.context.collection.objects.link(obj)
            obj["splatoon_generated"] = True
            obj["splatoon_owner"] = armature.name
            mesh = obj
    
    deselect_all_objects()
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = armature

    bpy.ops.object.parent_set(type='ARMATURE')
    
    # FIND THE MESH
    for child in armature.children:
        if "Body" in child.name and not "Hif" in child.name:
            deselect_all_objects()
            child.select_set(True)
            bpy.context.view_layer.objects.active = child
    
    # Get THE IMAGE
    a = bpy.data.images.new("btm_"+"{:02d}".format(index)+"_opa.png", 500, 500)
    a.colorspace_settings.name = "Non-Color"
    # GET THE MATERIAL
    mat = bpy.context.view_layer.objects.active.active_material
    # Texture
    node_tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node_tex.location = [-300,300]
    # LINK NODES
    links = mat.node_tree.links
    link = links.new(node_tex.outputs[0], mat.node_tree.nodes["Group"].inputs['Bottom_Mask'])
    #Find Texture
    for node in mat.node_tree.nodes:
        node.select = False
    
    node_tex.select = True
    mat.node_tree.nodes.active = node_tex

    node_tex.image = bpy.data.images.load(str(srcPath)+"/GearAlphaMask/btm_"+maskIndex[index]+"_opa.png")
    node_tex.image.colorspace_settings.name = 'Non-Color'

    # MATERIALS
    inka_color = (self.ink_A[0], self.ink_A[1], self.ink_A[2], 1)
    inkb_color = (self.ink_B[0], self.ink_B[1], self.ink_B[2], 1)
    
    mesh.active_material = mesh.active_material.copy()
    eyeblow_mat = mesh.active_material
    eyeblow_mat.node_tree.nodes["Group"].inputs[0].default_value = inka_color
    eyeblow_mat.node_tree.nodes["Group"].inputs[2].default_value = inkb_color
    
    deselect_all_objects()
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature


def create_inkling(self, context, type="inkling_F"):

    armature = None
    
    deselect_all_objects()
    src_path=str(srcPath) + "/"+type+"_body.blend"
 
    with bpy.data.libraries.load(src_path) as (data_from, data_to):
        data_to.objects = data_from.objects
 
    for obj in data_to.objects:
        bpy.context.collection.objects.link(obj)
        if obj.type == "ARMATURE":
            armature = obj
    
    deselect_all_objects()
    armature.name = self.name
    armature["splatoon_generated"] = True
    armature["splatoon_character_type"] = type
    bpy.context.view_layer.objects.active = armature
    for child in list(armature.children):
        child["splatoon_generated"] = True
        child["splatoon_owner"] = armature.name
    armature.select_set(True)

    # MATERIALS
    inka_color = (self.ink_A[0], self.ink_A[1], self.ink_A[2], 1)
    inkb_color = (self.ink_B[0], self.ink_B[1], self.ink_B[2], 1)
    
    #bpy.context.view_layer.objects.active.children[0].active_material = bpy.context.view_layer.objects.active.children[0].active_material.copy()
    body_mat = bpy.context.view_layer.objects.active.children[0].active_material
    skin_color = (self.skin[0], self.skin[1], self.skin[2], 1)
    cloth_color = (self.cloth[0], self.cloth[1], self.cloth[2], 1)
    eye_contour_color = (self.eye_contour[0], self.eye_contour[1], self.eye_contour[2], 1)
    body_mat.node_tree.nodes["Group"].inputs[0].default_value = skin_color
    body_mat.node_tree.nodes["Group"].inputs[1].default_value = cloth_color
    body_mat.node_tree.nodes["Group"].inputs[2].default_value = eye_contour_color
    body_mat.node_tree.nodes["Group"].inputs[3].default_value = inka_color
    body_mat.node_tree.nodes["Group"].inputs[5].default_value = inkb_color
    
    #bpy.context.view_layer.objects.active.children[5].active_material = bpy.context.view_layer.objects.active.children[5].active_material.copy()
    head_mat = bpy.context.view_layer.objects.active.children[5].active_material
    head_mat.node_tree.nodes["Group.002"].inputs[0].default_value = skin_color
    head_mat.node_tree.nodes["Group.002"].inputs[1].default_value = cloth_color
    head_mat.node_tree.nodes["Group.002"].inputs[2].default_value = eye_contour_color
    head_mat.node_tree.nodes["Group.002"].inputs[3].default_value = inka_color
    head_mat.node_tree.nodes["Group.002"].inputs[5].default_value = inkb_color
    
    #bpy.context.view_layer.objects.active.children[4].active_material = bpy.context.view_layer.objects.active.children[4].active_material.copy()
    bpy.context.view_layer.objects.active.children[4].active_material.node_tree.nodes[1].inputs[0].default_value = inka_color
    
    #bpy.context.view_layer.objects.active.children[2].active_material = bpy.context.view_layer.objects.active.children[2].active_material.copy()
    eyes_mat = bpy.context.view_layer.objects.active.children[2].active_material
    
    eye_texture = eyes_mat.node_tree.nodes[3].image = bpy.data.images.load(str(srcPath)+"/Eyes Textures/m_eye_alb."+ "{:02d}".format(self.eyes-1) +".png", check_existing=False)
    
    eyes_mat.node_tree.nodes[2].inputs[1].default_value = float(self.eyes)
    eyes_mat.node_tree.nodes[2].inputs[2].default_value = self.eyes_hue
    eyes_mat.node_tree.nodes[2].inputs[3].default_value = self.eyes_emission
    
    hif = bpy.context.view_layer.objects.active.children[3]
    hif.active_material.node_tree.nodes["Group"].inputs[0].default_value = inka_color
    
    # Hif
    # hif.data.shape_keys.key_blocks['Human'].driver_remove()
    driver = hif.data.shape_keys.key_blocks['Human'].driver_add("value")
    var1 = driver.driver.variables.new()
    var1.name = "var"
    var1.type = "TRANSFORMS"
    var1.targets[0].id = bpy.context.view_layer.objects.active
    var1.targets[0].transform_type = "LOC_Y"
    var1.targets[0].transform_space = "LOCAL_SPACE"
    var1.targets[0].bone_target = "Hif"
    driver.driver.expression = "var * -1 + 1"
    
    hif_mat = bpy.context.view_layer.objects.active.children[2].active_material
    # hif_mat.node_tree.nodes[1].inputs[3].driver_remove()
    driver2 = hif_mat.node_tree.nodes[1].inputs[3].driver_add("default_value")
    var2 = driver2.driver.variables.new()
    var2.name = "var"
    var2.type = "TRANSFORMS"
    var2.targets[0].id = bpy.context.view_layer.objects.active
    var2.targets[0].transform_type = "LOC_Y"
    var2.targets[0].transform_space = "LOCAL_SPACE"
    var2.targets[0].bone_target = "Hif"
    driver2.driver.expression = "var * -1 + 1"

    # Keep teeth visible and white when the Mouth_Joe/Mouth_Tooth bones are
    # posed open.  The bundled texture can become transparent/tinted in newer
    # Blender versions.
    for tooth in armature.children:
        if "Tooth" not in tooth.name or tooth.type != 'MESH':
            continue
        for slot, material in enumerate(list(tooth.data.materials)):
            if not material or not material.node_tree:
                continue
            material = material.copy()
            tooth.data.materials[slot] = material
            for group in material.node_tree.nodes:
                if group.type != 'GROUP' or not group.node_tree:
                    continue
                for node in group.node_tree.nodes:
                    if node.type != 'BSDF_PRINCIPLED':
                        continue
                    base = node.inputs.get('Base Color')
                    if base:
                        for link in list(group.node_tree.links):
                            if link.to_socket == base:
                                group.node_tree.links.remove(link)
                        base.default_value = (1, 1, 1, 1)
                    if node.inputs.get('Roughness'):
                        node.inputs['Roughness'].default_value = 0.4

    # Hair
    create_hair(self.hair, bpy.context.view_layer.objects.active, self, type)
    create_eyeblow(self.eyeblow, bpy.context.view_layer.objects.active, self, type)
    create_bottom(self.bottom, bpy.context.view_layer.objects.active, self)


class OBJECT_OT_add_inkling(Operator, AddObjectHelper):
    bl_idname = "mesh.player"
    bl_label = "Add Splatoon Player"
    bl_description = "Create a procedural Splatoon player."
    bl_options = {'REGISTER', 'UNDO'}
    
    type: bpy.props.EnumProperty(
        name="Type and Gender",
        description="Octoling/Inkling",
        items=(
            ('inkling_F', 'Inkling Female', 'An inkling girl'),
            ('inkling_M', 'Inkling Male', 'An inkling boy'),
            ('octoling_F', 'Octoling Female', 'An octoling girl'),
            ('octoling_M', 'Octoling Male', 'An octoling boy')
        )
    )
    name: bpy.props.StringProperty(
        name="Name",
        description="The player object name",
        maxlen=50,
        default="Inkling",
    )
    ink_A: FloatVectorProperty(  
       name="Ink Color",
       subtype='COLOR',
       default=(1, 0, 0),
       min=0.0, max=1.0,
       description="The player ink color"
    )
    ink_B: FloatVectorProperty(  
       name="Ennemie Ink Color",
       subtype='COLOR',
       default=(0, 1, 1),
       min=0.0, max=1.0,
       description="The player enemie ink color (when she take damages)"
    )
    skin: FloatVectorProperty(  
       name="Skin Tone",
       subtype='COLOR',
       default=(1, 0.59, 0.5),
       min=0.0, max=1.0,
       description="The player skin color"
    )
    cloth: FloatVectorProperty(  
       name="Cloth Color",
       subtype='COLOR',
       default=(0, 0, 0),
       min=0.0, max=1.0,
       description="The player cloth color"
    )
    eye_contour: FloatVectorProperty(  
       name="Eye Contour",
       subtype='COLOR',
       default=(0, 0, 0),
       min=0.0, max=1.0,
       description="The player eye_contour color"
    )
    eyes: bpy.props.IntProperty(  
        name="Eyes",
        description="The player eyes texture index",
        min=1, max=20,
        default=1
    )
    eyes_hue: bpy.props.FloatProperty(  
        name="Eyes Hue",
        default=0.5,
        min=0.0, max=1.0,
        description="The player eyes tone decalage"
    )
    eyes_emission: bpy.props.FloatProperty(  
        name="Eyes Emission",
        default=0,
        min=0.0, max=100.0,
        description="The player eyes luminosity"
    )
    hair: bpy.props.IntProperty(
        name="Hair",
        description="The hair index of the new player",
        min=0, max=15,
        default=0,
    )
    hair_emission: bpy.props.FloatProperty(  
        name="Hair Emission",
        default=0,
        min=0.0, max=100.0,
        description="The player hair luminosity"
    )
    eyeblow: bpy.props.IntProperty(
        name="Eyeblow",
        description="The eyeblow index of the new player",
        min=0, max=3,
        default=0,
    )
    bottom: bpy.props.IntProperty(
        name="Legwear",
        description="The legwear index of the new player",
        min=0, max=8,
        default=0,
    )

    def execute(self, context):
        create_inkling(self, context, self.type)
        return {'FINISHED'}


def _splatoon_scene_settings(scene):
    """Build the character settings object used by the legacy creation code."""
    return SimpleNamespace(
        type=scene.splatoon_type,
        name=scene.splatoon_name,
        ink_A=scene.splatoon_ink_a,
        ink_B=scene.splatoon_ink_b,
        skin=scene.splatoon_skin,
        cloth=scene.splatoon_cloth,
        eye_contour=scene.splatoon_eye_contour,
        eyes=scene.splatoon_eyes,
        eyes_hue=scene.splatoon_eyes_hue,
        eyes_emission=scene.splatoon_eyes_emission,
        hair=scene.splatoon_hair,
        hair_emission=scene.splatoon_hair_emission,
        eyeblow=scene.splatoon_eyeblow,
        bottom=scene.splatoon_bottom,
    )


def _set_group_input(obj, group_name, input_name, value):
    """Set a named shader-group input on every material slot of an object."""
    if obj is None or obj.type != 'MESH':
        return
    for material in obj.data.materials:
        if not material or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type != 'GROUP' or (group_name and node.name != group_name):
                continue
            socket = node.inputs.get(input_name)
            if socket is not None:
                socket.default_value = value


def apply_player_customization(scene):
    """Apply color and appearance values to the current player in place."""
    armature = getattr(scene, "splatoon_player_armature", None)
    if armature is None or armature.name not in bpy.data.objects:
        return False
    settings = _splatoon_scene_settings(scene)
    ink_a = (*settings.ink_A, 1)
    ink_b = (*settings.ink_B, 1)
    skin = (*settings.skin, 1)
    cloth = (*settings.cloth, 1)
    contour = (*settings.eye_contour, 1)

    for obj in list(armature.children):
        if obj.type != 'MESH':
            continue
        if "Body" in obj.name and "Hif" not in obj.name:
            _set_group_input(obj, "Group", "Skin", skin)
            _set_group_input(obj, "Group", "Cloth", cloth)
            _set_group_input(obj, "Group", "Eye Contour", contour)
            _set_group_input(obj, "Group", "Ink A", ink_a)
            _set_group_input(obj, "Group", "Ink B", ink_b)
            _set_group_input(obj, "Group.002", "Skin", skin)
            _set_group_input(obj, "Group.002", "Cloth", cloth)
            _set_group_input(obj, "Group.002", "Eye Contour", contour)
            _set_group_input(obj, "Group.002", "Ink A", ink_a)
            _set_group_input(obj, "Group.002", "Ink B", ink_b)
        elif "Hif Body" in obj.name or "Mouth" in obj.name:
            _set_group_input(obj, "Group", "Ink A", ink_a)
        elif "Eyes" in obj.name:
            for material in obj.data.materials:
                if not material or not material.node_tree:
                    continue
                for node in material.node_tree.nodes:
                    if node.name == "Group.002":
                        if node.inputs.get("Eye Index"):
                            node.inputs["Eye Index"].default_value = float(settings.eyes)
                        elif len(node.inputs) > 1:
                            node.inputs[1].default_value = float(settings.eyes)
                        if node.inputs.get("Hue"):
                            node.inputs["Hue"].default_value = settings.eyes_hue
                        elif len(node.inputs) > 2:
                            node.inputs[2].default_value = settings.eyes_hue
                        if node.inputs.get("Emission"):
                            node.inputs["Emission"].default_value = settings.eyes_emission
                        elif len(node.inputs) > 3:
                            node.inputs[3].default_value = settings.eyes_emission
                image = bpy.data.images.load(str(srcPath) + "/Eyes Textures/m_eye_alb." + f"{settings.eyes - 1:02d}" + ".png", check_existing=False)
                for node in material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image is not None:
                        node.image = image

    owner = armature.name
    for obj in bpy.context.scene.objects:
        if obj.get("splatoon_owner") != owner:
            continue
        if obj.type == 'MESH' and obj.name.startswith("Hair"):
            _set_group_input(obj, "Group", "Ink A", ink_a)
            _set_group_input(obj, "Group", "Ink B", ink_b)
            _set_group_input(obj, "Group", "Emission", settings.hair_emission)
        elif obj.type == 'MESH' and obj.name.startswith("Eyeblow"):
            _set_group_input(obj, "Group", "Ink A", ink_a)
            _set_group_input(obj, "Group", "Ink B", ink_b)
        elif obj.type == 'MESH' and obj.name.startswith("Bottom"):
            _set_group_input(obj, "Group", "Ink A", ink_a)
            _set_group_input(obj, "Group", "Ink B", ink_b)
    return True


class SPLATOON_OT_create_player(Operator):
    """Create a player from the persistent Splatoon sidebar settings."""
    bl_idname = "splatoon.create_player"
    bl_label = "Create / Update Player"
    bl_description = "Create a Splatoon player using the settings in this panel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = _splatoon_scene_settings(context.scene)
        remove_existing_player(context.scene)
        create_inkling(settings, context, settings.type)
        context.scene.splatoon_player_armature = bpy.context.view_layer.objects.active
        return {'FINISHED'}


class SPLATOON_PT_player(Panel):
    """Persistent replacement for Blender's temporary F9 customization panel."""
    bl_idname = "SPLATOON_PT_player"
    bl_label = "Splatoon Player"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Splatoon"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Shadorux Splatoon Tools", icon='USER')
        layout.label(text="Persistent character customization", icon='PINNED')

        player_box = layout.box()
        player_box.label(text="Player", icon='ARMATURE_DATA')
        player_box.prop(scene, "splatoon_type", text="Type")
        player_box.prop(scene, "splatoon_name", text="Name")
        player_box.operator(SPLATOON_OT_create_player.bl_idname, icon='ADD')

        colors = layout.box()
        colors.label(text="Colors", icon='COLOR')
        colors.prop(scene, "splatoon_ink_a", text="Ink A")
        colors.prop(scene, "splatoon_ink_b", text="Ink B")
        colors.prop(scene, "splatoon_skin", text="Skin")
        colors.prop(scene, "splatoon_cloth", text="Cloth")
        colors.prop(scene, "splatoon_eye_contour", text="Eye Contour")

        appearance = layout.box()
        appearance.label(text="Appearance", icon='HIDE_OFF')
        appearance.prop(scene, "splatoon_eyes", text="Eyes")
        appearance.prop(scene, "splatoon_eyes_hue", text="Eye Hue")
        appearance.prop(scene, "splatoon_eyes_emission", text="Eye Glow")
        appearance.prop(scene, "splatoon_hair", text="Hair")
        appearance.prop(scene, "splatoon_hair_emission", text="Hair Glow")
        appearance.prop(scene, "splatoon_eyeblow", text="Eyebrow")
        appearance.prop(scene, "splatoon_bottom", text="Legwear")

        layout.separator()
        layout.label(text="Maintained by Shadorux", icon='INFO')


def _register_scene_properties():
    scene = bpy.types.Scene
    scene.splatoon_type = bpy.props.EnumProperty(
        name="Type and Gender",
        items=(
            ('inkling_F', 'Inkling Female', 'An inkling girl'),
            ('inkling_M', 'Inkling Male', 'An inkling boy'),
            ('octoling_F', 'Octoling Female', 'An octoling girl'),
            ('octoling_M', 'Octoling Male', 'An octoling boy'),
        ),
        default='inkling_F',
    )
    scene.splatoon_name = bpy.props.StringProperty(name="Name", maxlen=50, default="Inkling")
    scene.splatoon_ink_a = bpy.props.FloatVectorProperty(name="Ink Color", subtype='COLOR', size=3, default=(1, 0, 0), min=0, max=1)
    scene.splatoon_ink_b = bpy.props.FloatVectorProperty(name="Enemy Ink Color", subtype='COLOR', size=3, default=(0, 1, 1), min=0, max=1)
    scene.splatoon_skin = bpy.props.FloatVectorProperty(name="Skin Tone", subtype='COLOR', size=3, default=(1, 0.59, 0.5), min=0, max=1)
    scene.splatoon_cloth = bpy.props.FloatVectorProperty(name="Cloth Color", subtype='COLOR', size=3, default=(0, 0, 0), min=0, max=1)
    scene.splatoon_eye_contour = bpy.props.FloatVectorProperty(name="Eye Contour", subtype='COLOR', size=3, default=(0, 0, 0), min=0, max=1)
    scene.splatoon_eyes = bpy.props.IntProperty(name="Eyes", min=1, max=20, default=1)
    scene.splatoon_eyes_hue = bpy.props.FloatProperty(name="Eyes Hue", min=0, max=1, default=0.5)
    scene.splatoon_eyes_emission = bpy.props.FloatProperty(name="Eyes Emission", min=0, max=100, default=0)
    scene.splatoon_hair = bpy.props.IntProperty(name="Hair", min=0, max=15, default=0)
    scene.splatoon_hair_emission = bpy.props.FloatProperty(name="Hair Emission", min=0, max=100, default=0)
    scene.splatoon_eyeblow = bpy.props.IntProperty(name="Eyebrow", min=0, max=3, default=0)
    scene.splatoon_bottom = bpy.props.IntProperty(name="Legwear", min=0, max=8, default=0)
    scene.splatoon_player_armature = bpy.props.PointerProperty(name="Generated Player", type=bpy.types.Object)


def _unregister_scene_properties():
    for name in (
        "splatoon_type", "splatoon_name", "splatoon_ink_a", "splatoon_ink_b",
        "splatoon_skin", "splatoon_cloth", "splatoon_eye_contour", "splatoon_eyes",
        "splatoon_eyes_hue", "splatoon_eyes_emission", "splatoon_hair",
        "splatoon_hair_emission", "splatoon_eyeblow", "splatoon_bottom",
        "splatoon_player_armature",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)


# Registration
def add_inkling_button(self, context):
    self.layout.operator(
        OBJECT_OT_add_inkling.bl_idname,
        text="Splatoon Player",
        icon='USER')

def register():
    bpy.utils.register_class(OBJECT_OT_add_inkling)
    bpy.utils.register_class(SPLATOON_OT_create_player)
    bpy.utils.register_class(SPLATOON_PT_player)
    _register_scene_properties()
    bpy.types.VIEW3D_MT_mesh_add.append(add_inkling_button)
    cloth_import.register()
    weapon_import.register()
    item_import.register()
    fast_squid.register()
    fast_octopus.register()

def unregister():
    fast_octopus.unregister()
    fast_squid.unregister()
    item_import.unregister()
    weapon_import.unregister()
    cloth_import.unregister()
    bpy.utils.unregister_class(OBJECT_OT_add_inkling)
    _unregister_scene_properties()
    bpy.utils.unregister_class(SPLATOON_PT_player)
    bpy.utils.unregister_class(SPLATOON_OT_create_player)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_inkling_button)

if __name__ == "__main__":
    register()
