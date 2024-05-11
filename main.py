# -------------------- IMPORTS -------------------- #
from random import random, randrange

from flask import Flask, render_template, request, redirect, url_for
from flask_bootstrap import Bootstrap  # install with pip via terminal
from datetime import datetime
import os  # used for accessing environment variables
from random import randrange

import recipe_forms
# my classes
from sqlite_handlers import execute_query, execute_insert_script, execute_update_script, execute_delete_script\
    , execute_general_sql
from recipe_forms import RecipeHeaderForm, RecipeInstructionForm, RecipeIngredientForm, RecipeNutritionForm\
    , RecipeSearchForm
import emailer


# -------------------- FLASK -------------------- #
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
Bootstrap(app)


# ------------------------------ EMAILER ------------------------------ #
email_sender = emailer.Emailer()


# -------------------- CONSTANTS -------------------- #
QUICK_MEAL_THRESHOLD = 25  # meals taking less than this much time to cook will be marked as fast
LOW_FAT_MEAL_THRESHOLD = 5  # meals with less than this much saturated fat / serving will be marked as low fat
LOW_CAL_THRESHOLD = 800  # meals under this calorie count are marked as low cal
DEFAULT_EDITOR_PAGE_INDEX = '-1'
NEW_RECORD_PAGE_INDEX = '0'
# TODO set to true for prod
prod_mode = True  # master toggle to switch between DEV and PROD modes


# -------------------- DB METHODS -------------------- #
def get_ingredients(recipe_id: str):
    query_string = "SELECT IngredientName, CBIngredientPrep.ShortName as Prep, Quantity" \
                   ", CBIngredientName.RecipeID as RelatedRecipeID " \
                   ", CBIngredientUnit.ShortName as Units, IngredientID " \
                   "FROM CBIngredient " \
                   "JOIN CBIngredientName ON CBIngredient.IngredientNameID = CBIngredientName.IngredientNameID " \
                   "JOIN CBIngredientPrep ON CBIngredientPrep.PrepID = CBIngredient.PrepID " \
                   "JOIN CBIngredientUnit ON CBIngredientUnit.IngredientUnitID = CBIngredient.IngredientUnitID " \
                   f"WHERE CBIngredient.RecipeID = {recipe_id} " \
                   f"ORDER BY IngredientName"
    return execute_query(query_string)


def get_nutrition(recipe_id: str):
    query_string = "SELECT CBElementName.ShortName as ElementName, CBElementName.ElementNameID as ElementNameCode" \
                   ", NutritionValue, CBElementUnit.ShortName as Units, CBElementUnit.ElementUnitID as UnitsCode" \
                   ", NutritionID " \
                   "FROM CBNutrition Element " \
                   "JOIN CBElementName ON CBElementName.ElementNameID = Element.ElementNameID " \
                   "JOIN CBElementUnit ON CBElementUnit.ElementUnitID = Element.ElementUnitID " \
                   f"WHERE Element.RecipeID = {recipe_id}"
    return execute_query(query_string)


def get_instructions(recipe_id: str):
    query_string = "SELECT StepNumber, StepText, InstructionID " \
                   "FROM CBInstructions " \
                   f"WHERE RecipeID={recipe_id} " \
                   "ORDER BY RecipeID ASC, StepNumber ASC"
    return execute_query(query_string)


def get_recipe_header(recipe_id: str):
    query_string = "SELECT RecipeName, CookingTime, Servings, Source, CreationGMT, RecipeTypeID " \
                   "FROM CBRecipe " \
                   f"WHERE RecipeID = {recipe_id}"
    return execute_query(query_string)


def get_badges(recipe_id: str):
    query_string = "SELECT BadgeName, BadgeIconAddress " \
                   "FROM CBBadge " \
                   "JOIN CBRecipeBadge ON CBRecipeBadge.BadgeID = CBBadge.BadgeID " \
                   f"WHERE RecipeID = {recipe_id}"
    return execute_query(query_string)


def get_recent_recipes():
    query_string = "SELECT LongName || ' - ' || RecipeName AS RecipeName, CreationGMT, RecipeID " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeType ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "ORDER BY CreationGMT DESC " \
                   "LIMIT 10"
    results = execute_query(query_string)
    return results


def get_site_stats():
    query_string = "SELECT CBRecipeType.LongName 'Category', COUNT(*) 'Count', 1 " \
                   "FROM CBRecipeType " \
                   "JOIN CBRecipe ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "GROUP BY CBRecipeType.LongName " \
                   "UNION SELECT 'TOTAL', COUNT(*), 0 " \
                   "FROM CBRecipe " \
                   "ORDER BY 3 DESC, 1 ASC"
    results = execute_query(query_string)
    return results


def update_header(recipe_id: str, new_recipe_name: str, new_recipe_time: int
                  , new_recipe_servings: int, new_recipe_source: str, recipe_type_id: str):
    update_script = "UPDATE CBRecipe " \
                    f'SET RecipeName = "{new_recipe_name}"' \
                    f', CookingTime = {new_recipe_time}' \
                    f', Servings = {new_recipe_servings}' \
                    f', Source = "{new_recipe_source}" ' \
                    f', RecipeTypeID = {recipe_type_id} ' \
                    f'WHERE RecipeID = {recipe_id}'
    execute_update_script(update_script)

    # add quick badge based on cook time, if applicable
    if int(new_recipe_time) <= QUICK_MEAL_THRESHOLD:
        badge_name = "Quick Prep"
        insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                        f'SELECT {recipe_id}, BadgeID ' \
                        'FROM CBBadge ' \
                        f'WHERE BadgeName = "{badge_name}" ' \
                        'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                        'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                        f'AND BadgeName = "{badge_name}" ' \
                        f'WHERE RecipeID = {recipe_id}) ' \
                        '= 0'
        execute_insert_script(insert_script)
    elif int(new_recipe_time) > QUICK_MEAL_THRESHOLD:
        delete_script = 'DELETE FROM CBRecipeBadge ' \
                        f'WHERE RecipeID = {recipe_id} AND BadgeID = 1'
        execute_delete_script(delete_script)


def update_instruction(instruction_id: str, new_instruction: str):
    update_script = "UPDATE CBInstructions " \
                    f'SET StepText = "{new_instruction}" ' \
                    f'WHERE InstructionID = {instruction_id}'
    execute_update_script(update_script)


def update_nutrition(recipe_id: str, nutrition_id: str, new_nutrition_name_code: str, new_nutrition_value: float
                     , new_nutrition_unit_code: str):
    update_script = "UPDATE CBNutrition " \
                    f'SET ElementNameID = "{new_nutrition_name_code}"' \
                    f', NutritionValue = {new_nutrition_value}' \
                    f', ElementUnitID = {new_nutrition_unit_code} ' \
                    f'WHERE NutritionID = {nutrition_id}'
    execute_update_script(update_script)

    # process changes to badges
    if new_nutrition_name_code == '9':  # saturated fat
        if float(new_nutrition_value) <= float(LOW_FAT_MEAL_THRESHOLD):
            # add low-fat badge, if not already present
            badge_name = "Low Fat"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            f'SELECT {recipe_id}, BadgeID ' \
                            'FROM CBBadge ' \
                            f'WHERE BadgeName = "{badge_name}" ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            f'AND BadgeName = "{badge_name}" ' \
                            f'WHERE RecipeID = {recipe_id}) ' \
                            '= 0'
            execute_insert_script(insert_script)
        else:   # above fat threshold
            delete_script = 'DELETE FROM CBRecipeBadge ' \
                            f'WHERE RecipeID = {recipe_id} AND BadgeID = 3'  # low fat badge ID
            execute_delete_script(delete_script)
    elif new_nutrition_name_code == '1':  # calories
        if float(new_nutrition_value) <= float(LOW_CAL_THRESHOLD):
            # add low-cal badge, if not already present
            badge_name = "Low Calorie"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            f'SELECT {recipe_id}, BadgeID ' \
                            'FROM CBBadge ' \
                            f'WHERE BadgeName = "{badge_name}" ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            f'AND BadgeName = "{badge_name}" ' \
                            f'WHERE RecipeID = {recipe_id}) ' \
                            '= 0'
            execute_insert_script(insert_script)
        else:   # above calorie threshold
            delete_script = 'DELETE FROM CBRecipeBadge ' \
                            f'WHERE RecipeID = {recipe_id} AND BadgeID = 2'  # low cal badge ID
            execute_delete_script(delete_script)


def update_ingredient(ingredient_id: str, new_ingredient_name_id: str, new_quantity: float
                      , new_prep_id: str, new_unit_id: str):
    update_script = "UPDATE CBIngredient " \
                    f'SET IngredientNameID = {new_ingredient_name_id}' \
                    f', Quantity = {new_quantity}' \
                    f', PrepID = {new_prep_id}' \
                    f', IngredientUnitID = {new_unit_id} ' \
                    f'WHERE IngredientID = {ingredient_id}'
    execute_update_script(update_script)
    # TODO: Check if the ingredient has been changed to something that alters the vegetarian status


def create_header(new_recipe_name: str, new_recipe_time: int
                  , new_recipe_servings: int, new_recipe_source: str, new_creationGMT: str, recipe_type_id: str):
    # inserts a new record into the header table, brings back the new ID.
    insert_script = 'INSERT INTO CBRecipe(RecipeName, CookingTime, Servings, Source, CreationGMT, RecipeTypeID)' \
                    f'SELECT "{new_recipe_name}", {new_recipe_time}, {new_recipe_servings}, "{new_recipe_source}"' \
                    f', "{new_creationGMT}", {recipe_type_id} '
    new_id = execute_insert_script(insert_script, table_name='CBRecipe', id_column='RecipeID')

    # now add badge based on cook time, if applicable
    if int(new_recipe_time) <= QUICK_MEAL_THRESHOLD:
        insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                        f'SELECT "{new_id}", 1'
        execute_insert_script(insert_script)

    # assume all recipes are vegetarian off the bat. only toggle to No when an ingredient is added which is not.
    badge_id_veggie = 4
    insert_script = f"INSERT INTO CBRecipeBadge (RecipeID, BadgeID) SELECT {new_id}, {badge_id_veggie}"
    execute_insert_script(insert_script)

    return new_id


def create_instruction(recipe_id: str, new_instruction: str):
    # query for max instruction step number
    query_string = "SELECT MAX(StepNumber) as MaxStep " \
                   "FROM CBInstructions " \
                   f"WHERE RecipeID = {recipe_id}"
    max_step = execute_query(query_string)[0]["MaxStep"]
    if max_step is None:
        max_step = 0
    # increment
    new_step_number = int(max_step) + 1
    # insert
    insert_script = 'INSERT INTO CBInstructions(RecipeID, StepNumber, StepText)' \
                    f'SELECT {recipe_id}, {new_step_number}, "{new_instruction}" '
    new_id = execute_insert_script(insert_script, table_name='CBInstructions', id_column='InstructionID')
    return new_id


def create_nutrition(recipe_id: str, new_nutrition_name_code: str, new_nutrition_value: float
                     , new_nutrition_unit_code: str):
    # inserts a new record into the header table, brings back the new ID.
    insert_script = 'INSERT INTO CBNutrition(RecipeID, ElementNameID, NutritionValue, ElementUnitID)' \
                    f'SELECT {recipe_id}, {new_nutrition_name_code}, {new_nutrition_value}' \
                    f', {new_nutrition_unit_code} '
    new_id = execute_insert_script(insert_script, table_name='CBNutrition', id_column='NutritionID')
    # check if this new element deserves a badge
    if new_nutrition_name_code == '9':  # sat fat
        if float(new_nutrition_value) <= float(LOW_FAT_MEAL_THRESHOLD):
            # add low-fat badge, if not already present
            badge_name = "Low Fat"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            f'SELECT {recipe_id}, BadgeID ' \
                            'FROM CBBadge ' \
                            f'WHERE BadgeName = "{badge_name}" ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            f'AND BadgeName = "{badge_name}" ' \
                            f'WHERE RecipeID = {recipe_id}) ' \
                            '= 0'
            execute_insert_script(insert_script)
    elif new_nutrition_name_code == '1':  # calories
        if float(new_nutrition_value) <= float(LOW_CAL_THRESHOLD):
            # add low-cal badge, if not already present
            badge_name = "Low Calorie"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            f'SELECT {recipe_id}, BadgeID ' \
                            'FROM CBBadge ' \
                            f'WHERE BadgeName = "{badge_name}" ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            f'AND BadgeName = "{badge_name}" ' \
                            f'WHERE RecipeID = {recipe_id}) ' \
                            '= 0'
            execute_insert_script(insert_script)
    return new_id


def create_ingredient_name(ingredient_name: str, is_vegetarian: str, search_name: str, linked_recipe: int):
    insert_script = 'INSERT INTO CBIngredientName(IngredientName, IsVegetarian, SearchName, RecipeID) ' \
                    f'SELECT "{ingredient_name}", "{is_vegetarian}", "{search_name}" ' \
                    f', IIF({linked_recipe} == -1, NULL, {linked_recipe}) '
    new_id = execute_insert_script(insert_script, table_name='CBIngredientName', id_column='IngredientNameID')
    return new_id


def create_ingredient_prep(ingredient_prep: str):
    insert_script = 'INSERT INTO CBIngredientPrep(ShortName, LongName) ' \
                    f'SELECT "{ingredient_prep}", "{ingredient_prep}" '
    new_id = execute_insert_script(insert_script, table_name='CBIngredientPrep', id_column='PrepID')
    return new_id


def create_ingredient_unit(ingredient_unit: str):
    insert_script = 'INSERT INTO CBIngredientUnit(ShortName, LongName) ' \
                    f'SELECT "{ingredient_unit}", "{ingredient_unit}"'
    new_id = execute_insert_script(insert_script, table_name='CBIngredientUnit', id_column='IngredientUnitID')
    return new_id


def create_ingredient(recipe_id: str, ingredient_name_id: str, quantity: str, prep_id: str, ingredient_unit_id: str):
    insert_script = 'INSERT INTO CBIngredient(RecipeID, IngredientNameID, Quantity, PrepID, IngredientUnitID) ' \
                    f'SELECT {recipe_id}, {ingredient_name_id}, {quantity}, {prep_id}, {ingredient_unit_id} '
    new_id = execute_insert_script(insert_script, table_name='CBIngredient', id_column='IngredientID')

    # check if this ingredient is vegetarian
    query_string = 'SELECT IsVegetarian ' \
                   'FROM CBIngredientName ' \
                   f'WHERE IngredientNameID = {ingredient_name_id}'
    is_vegetarian = execute_query(query_string)[0]['IsVegetarian']

    # assume all recipes are vegetarian off the bat. only toggle to No when an ingredient is added which is not.
    if is_vegetarian == 'N':
        badge_id_veggie = 4
        delete_script = f"DELETE FROM CBRecipeBadge WHERE RecipeID = {recipe_id} AND BadgeID = {badge_id_veggie}"
        execute_delete_script(delete_script)

    return new_id


# ------------------- FORM HANDLERS --------------------- #
def configure_header_form(recipe_id: str, recipe_header: dict):
    print(f"configuring header form for recipe_id: {recipe_id}")
    form = RecipeHeaderForm()
    # Initialize Header Fields
    if recipe_id == NEW_RECORD_PAGE_INDEX:
        form.recipe_name.data = ''
        form.recipe_time.data = 1
        form.recipe_servings.data = 1
        form.recipe_source.data = ''
        form.recipe_creationGMT.data = datetime.now()
        form.recipe_type.process_data(1)   # default CodeValue: dinner
        form.recipe_id.data = recipe_id
    else:
        form.recipe_name.data = recipe_header['RecipeName']
        form.recipe_time.data = recipe_header['CookingTime']
        form.recipe_servings.data = recipe_header['Servings']
        form.recipe_source.data = recipe_header['Source']
        form.recipe_creationGMT.data = recipe_header['CreationGMT']
        form.recipe_type.process_data(recipe_header['RecipeTypeID'])
        form.recipe_id.data = recipe_id

    return form


def configure_instruction_form(recipe_id: str, instruction_id: str, instructions: dict):
    print(f"configuring instruction form for instruction_id: {instruction_id}")
    form = RecipeInstructionForm()
    # Initialize instruction Fields
    if instruction_id == NEW_RECORD_PAGE_INDEX or instruction_id == DEFAULT_EDITOR_PAGE_INDEX:
        # default page (no editing) OR Add new step page
        form.instruction.data = ' '
        form.recipe_id.data = recipe_id
        form.instruction_id.data = instruction_id
    else:
        # get the step text which corresponds to this specific instruction
        step_text = ''
        for instruction in instructions:
            if str(instruction['InstructionID']) == instruction_id:
                step_text = instruction['StepText']
                break
        form.instruction.data = step_text
        form.recipe_id.data = recipe_id
        form.instruction_id.data = instruction_id
    return form


def configure_nutrition_form(recipe_id: str, nutrition_id: str, nutrition_facts: dict):
    print(f"configuring nutrition form for nutrition_id: {nutrition_id}")
    form = RecipeNutritionForm()
    # Initialize instruction Fields
    nutrition_name_code = '1'
    nutrition_value = None
    nutrition_unit = '2'    # grams is default
    if nutrition_id == DEFAULT_EDITOR_PAGE_INDEX:
        # default page (no editing)
        form.nutrition_name.data = nutrition_name_code
        form.nutrition_value.data = nutrition_value
        form.nutrition_unit.data = nutrition_unit
    elif nutrition_id == NEW_RECORD_PAGE_INDEX:
        # Add new element page
        form.nutrition_name.data = nutrition_name_code
        form.nutrition_value.data = nutrition_value
        form.nutrition_unit.data = nutrition_unit
    else:
        # get the current data associated with this ID
        for fact in nutrition_facts:
            if str(fact['NutritionID']) == nutrition_id:
                nutrition_name_code = fact['ElementNameCode']
                nutrition_value = fact['NutritionValue']
                nutrition_unit = fact['UnitsCode']
                break
        query_string = "SELECT ElementNameID, LongName FROM CBElementName ORDER BY 2 ASC"
        nutrition_element_names = execute_query(query_string, convert_to_dict=False)
        form.nutrition_name.choices = nutrition_element_names
        form.nutrition_name.data = str(nutrition_name_code)
        form.nutrition_value.data = nutrition_value
        query_string = "SELECT ElementUnitID, LongName FROM CBElementUnit ORDER BY 2 ASC"
        nutrition_units = execute_query(query_string, convert_to_dict=False)
        form.nutrition_unit.choices = nutrition_units
        form.nutrition_unit.data = str(nutrition_unit)
    form.recipe_id.data = recipe_id
    form.nutrition_id.data = nutrition_id
    return form


def configure_ingredient_form(recipe_id: str, ingredient_id: str):
    print(f"configuring ingredient form for ingredient_id: {ingredient_id}")
    form = RecipeIngredientForm()
    form.ingredient_id.data = ingredient_id
    form.recipe_id.data = recipe_id
    default_combo_value = '0'
    default_quantity = 1
    if ingredient_id == DEFAULT_EDITOR_PAGE_INDEX:
        # default view
        form.ingredient_name_new.data = None
        form.ingredient_name.data = default_combo_value

        form.ingredient_prep_new.data = None
        form.ingredient_prep.data = default_combo_value

        form.ingredient_unit_new.data = None
        form.ingredient_unit.data = default_combo_value

        form.ingredient_quantity.data = default_quantity

    elif ingredient_id == NEW_RECORD_PAGE_INDEX:
        # add view
        form.ingredient_name_new.data = None
        form.ingredient_name.data = default_combo_value
        query_string = "SELECT IngredientNameID, IngredientName FROM CBIngredientName ORDER BY 2 ASC"
        form.ingredient_name.choices = execute_query(query_string, convert_to_dict=False)
        form.is_vegetarian.data = 'y'  # most ingredients are vegetarian, so default to yes
        form.search_name.process_data("Not Searchable")
        form.ingredient_prep_new.data = None
        form.ingredient_prep.data = default_combo_value
        query_string = "SELECT PrepID, LongName FROM CBIngredientPrep ORDER BY 2 ASC"
        form.ingredient_prep.choices = execute_query(query_string, convert_to_dict=False)
        form.ingredient_prep.process_data(1)    # default value which corresponds to 'None'
        form.ingredient_unit_new.data = None
        form.ingredient_unit.data = default_combo_value
        query_string = "SELECT IngredientUnitID, LongName FROM CBIngredientUnit ORDER BY 2 ASC"
        form.ingredient_unit.choices = execute_query(query_string, convert_to_dict=False)

        form.ingredient_quantity.data = default_quantity

    else:
        # Edit existing record
        # get the current data associated with this ID
        query_string = "SELECT IngredientNameID, IngredientUnitID, PrepID, Quantity " \
                "FROM CBIngredient " \
                f"WHERE IngredientID = {ingredient_id}"
        ingredient_data = execute_query(query_string)
        form.ingredient_name_new.data = None
        query_string = "SELECT IngredientNameID, IngredientName FROM CBIngredientName ORDER BY 2 ASC"
        form.ingredient_name.choices = execute_query(query_string, convert_to_dict=False)
        form.ingredient_name.process_data(int(ingredient_data[0]["IngredientNameID"]))

        form.ingredient_prep_new.data = None
        query_string = "SELECT PrepID, LongName FROM CBIngredientPrep ORDER BY 2 ASC"
        form.ingredient_prep.choices = execute_query(query_string, convert_to_dict=False)
        form.ingredient_prep.process_data(int(ingredient_data[0]["PrepID"]))

        form.ingredient_unit_new.data = None
        query_string = "SELECT IngredientUnitID, LongName FROM CBIngredientUnit ORDER BY 2 ASC"
        form.ingredient_unit.choices = execute_query(query_string, convert_to_dict=False)
        form.ingredient_unit.process_data(int(ingredient_data[0]["IngredientUnitID"]))

        form.ingredient_quantity.data = ingredient_data[0]["Quantity"]

    return form


def configure_search_form():
    form = RecipeSearchForm()
    form.recipe_type.process_data(0)    # set default option to "all"
    return form


def process_header_form(form):
    print("processing header form: ")
    print(form)
    # pull data from the form
    recipe_name = form["recipe_name"]
    recipe_time = form["recipe_time"]
    recipe_servings = form["recipe_servings"]
    recipe_source = form["recipe_source"]
    recipe_type_id = form["recipe_type"]
    recipe_id = form["recipe_id"]
    recipe_creationGMT = form["recipe_creationGMT"]
    if recipe_id != NEW_RECORD_PAGE_INDEX:
        update_header(recipe_id=recipe_id, new_recipe_name=recipe_name, new_recipe_time=recipe_time
                      , new_recipe_servings=recipe_servings, new_recipe_source=recipe_source
                      , recipe_type_id=recipe_type_id)
    else:
        recipe_id = create_header(new_recipe_name=recipe_name, new_recipe_time=recipe_time
                                  , new_recipe_servings=recipe_servings, new_recipe_source=recipe_source
                                  , new_creationGMT=recipe_creationGMT, recipe_type_id=recipe_type_id)
    return recipe_id


def process_instruction_form(form):
    print("processing instruction form: ")
    print(form)
    # pull data from the form
    recipe_id = form["recipe_id"]
    instruction_id = form["instruction_id"]
    instruction = form["instruction"]
    if instruction_id != NEW_RECORD_PAGE_INDEX:
        update_instruction(instruction_id=instruction_id, new_instruction=instruction)
    else:
        instruction_id = create_instruction(recipe_id=recipe_id, new_instruction=instruction)
    return instruction_id


def process_nutrition_form(form):
    print("processing nutrition form: ")
    # pull data from the form
    nutrition_name_code = form["nutrition_name"]
    nutrition_value = form["nutrition_value"]
    nutrition_unit_code = form["nutrition_unit"]
    recipe_id = form["recipe_id"]
    nutrition_id = form["nutrition_id"]
    if nutrition_id != NEW_RECORD_PAGE_INDEX:
        # editing an existing record
        update_nutrition(recipe_id=recipe_id, nutrition_id=nutrition_id, new_nutrition_name_code=nutrition_name_code
                         , new_nutrition_value=nutrition_value, new_nutrition_unit_code=nutrition_unit_code)
    else:
        # adding a new record
        nutrition_id = create_nutrition(recipe_id=recipe_id, new_nutrition_name_code=nutrition_name_code
                                        , new_nutrition_value=nutrition_value
                                        , new_nutrition_unit_code=nutrition_unit_code)
    return nutrition_id


def process_ingredient_form(form):
    print("processing ingredient form: ")
    # pull data from the form
    recipe_id = form["recipe_id"]
    ingredient_name_code = form["ingredient_name"]
    new_ingredient_name = form["ingredient_name_new"]
    if "is_vegetarian" in form:  # when a checkbox is not checked it doesn't come back at all, because WTForms is dumb.
        is_vegetarian = 'Y'
    else:
        is_vegetarian = 'N'
    search_name = form["search_name"]
    new_search_name = form["search_name_new"]
    ingredient_prep_code = form["ingredient_prep"]
    new_ingredient_prep = form["ingredient_prep_new"]
    ingredient_quantity = form["ingredient_quantity"]
    ingredient_unit_code = form["ingredient_unit"]
    new_ingredient_unit = form["ingredient_unit_new"]
    ingredient_id = form["ingredient_id"]
    linked_recipe = form["linked_recipe"]

    if ingredient_id == '0':    # creating a new ingredient record
        # check if the new_ fields are populated.
        if new_ingredient_name != '':
            # overwrite combo field value with manually entered text, if any
            if new_search_name != '':
                search_name = new_search_name
            # create new ingredient record if new name text field was used
            ingredient_name_code = create_ingredient_name(new_ingredient_name, is_vegetarian, search_name
                                                          , linked_recipe)
        if new_ingredient_prep != '':
            # create new ingredient record if new name text field was used
            ingredient_prep_code = create_ingredient_prep(new_ingredient_prep)
        if new_ingredient_unit != '':
            # create new ingredient record if new name text field was used
            ingredient_unit_code = create_ingredient_unit(new_ingredient_unit)
        ingredient_id = create_ingredient(recipe_id, ingredient_name_code, ingredient_quantity
                                          , ingredient_prep_code, ingredient_unit_code)
    else:   # editing an existing ingredient
        update_ingredient(ingredient_id, ingredient_name_code, ingredient_quantity
                          , ingredient_prep_code, ingredient_unit_code)
    return ingredient_id


def process_search_form(form):
    print("processing search form: ")
    recipe_type = int(form['recipe_type'])
    ingredient_search_name = str(form['recipe_ingredient'])
    if ingredient_search_name == 'All':
        ingredient_search_name = '%'
    search_keyword = '%' + form['search_term'] + '%'

    # PROCESS BADGES
    badge_query_string = ""
    if "quick_meal" in form:    # presence of a boolean field means it was checked off.
        badge_query_string += "JOIN CBRecipeBadge QuickMeal ON QuickMeal.RecipeID = CBRecipe.RecipeID " \
                              "AND QuickMeal.BadgeID = 1 "
    if "low_calorie" in form:   # presence of a boolean field means it was checked off.
        badge_query_string += "JOIN CBRecipeBadge LowCalorie ON LowCalorie.RecipeID = CBRecipe.RecipeID " \
                              "AND LowCalorie.BadgeID = 2 "
    if "low_fat" in form:   # presence of a boolean field means it was checked off.
        badge_query_string += "JOIN CBRecipeBadge LowFat ON LowFat.RecipeID = CBRecipe.RecipeID " \
                              "AND LowFat.BadgeID = 3 "
    if "vegetarian" in form:    # presence of a boolean field means it was checked off.
        badge_query_string += "JOIN CBRecipeBadge Vegetarian ON Vegetarian.RecipeID = CBRecipe.RecipeID " \
                              "AND Vegetarian.BadgeID = 4 "
    recipe_type_query_string = ""
    if recipe_type != 0:
        recipe_type_query_string = f"AND CBRecipe.RecipeTypeID = '{recipe_type}'"

    query_string = "SELECT DISTINCT CBRecipe.RecipeID" \
                   f", IIF({recipe_type} = 0, CBRecipeType.ShortName || ' - ', '') " \
                   "|| RecipeName " \
                   "|| ' (' " \
                   "|| CAST(CookingTime AS VarChar(10)) " \
                   "|| 'min)' AS RecipeName " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeType ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "JOIN CBIngredient ON CBRecipe.RecipeID = CBIngredient.RecipeID " \
                   "JOIN CBIngredientName ON CBIngredient.IngredientNameID = CBIngredientName.IngredientNameID " \
                   f"AND CBIngredientName.SearchName LIKE '{ingredient_search_name}' " \
                   "" + badge_query_string + \
                   f"WHERE RecipeName LIKE '{search_keyword}' " + recipe_type_query_string + " ORDER BY 2"
    search_results = execute_query(query_string)
    return search_results


def process_database_form(form):
    sql_string = form["SQL_string"]
    result = execute_general_sql(sql_string)
    return result


def process_email_form(form):
    message = ""
    if form["recipe_name"] is not None:
        message += "Recipe Name: " + form["recipe_name"].data + "\n"
    if form["recipe_source"] is not None:
        message += "Recipe Source: " + str(form["recipe_source"].data) + "\n"
    if form["total_time"] is not None:
        message += "Time: " + str(form["total_time"].data) + "\n"
    if form["servings"] is not None:
        message += "Servings: " + str(form["servings"].data) + "\n"
    if form["instructions"] is not None:
        message += "Instructions: " + str(form["instructions"].data) + "\n"
    if form["ingredients"] is not None:
        message += "Ingredients: " + str(form["ingredients"].data) + "\n"
    if form["nutrition"] is not None:
        message += "Nutrition: " + str(form["nutrition"].data) + "\n"
    email_sender.send_message(subject="New recipe submitted!."
                              , message=message)


# -------------------- UTILITY -------------------- #
def create_nav_controls(home_button: bool = False, recipe_button: bool = False, recipe_id: str = "0"
                        , edit_button: bool = False):
    # currently simple converts the inputs into a JSON / Dict which can be read by the nav html
    if prod_mode:
        edit_button = False  # edit button never allowed in prod mode
    return {
        "home": home_button
        , "edit": edit_button
        , "recipe": recipe_button
        , "recipeID": recipe_id
    }


def get_badge_definitions():
    definitions = [
        f"Low Fat: <= {LOW_FAT_MEAL_THRESHOLD}g Sat Fat,   Low Cal: <= {LOW_CAL_THRESHOLD}cal,"
        , f"Quick Meal: <= {QUICK_MEAL_THRESHOLD}min total prep & cook time"
    ]
    return definitions


# -------------------- APP ROUTES -------------------- #
@app.route('/', methods=["GET", "POST"])
def home():
    print(f"{request.method} method request for home called")
    # get data for recent recipe widget
    site_stats = get_site_stats()
    recent_recipes = get_recent_recipes()
    search_form = configure_search_form()
    badge_definitions = get_badge_definitions()
    search_results = []
    message = ""
    if request.method == 'POST':
        search_results = process_search_form(request.form)
        if len(search_results) == 0:
            message = "No recipes were found to match your search conditions."
        elif "random" in request.form:
            result_count = len(search_results)
            index = randrange(result_count)
            return redirect(url_for('recipe', recipe_id=search_results[index]["RecipeID"]))
        return render_template("index.html"
                               , recent_recipes=recent_recipes
                               , site_stats=site_stats
                               , search_form=search_form
                               , search_results=search_results
                               , message=message
                               , prod_mode=prod_mode
                               , badge_definitions=badge_definitions)
    else:
        return render_template("index.html"
                               , recent_recipes=recent_recipes
                               , site_stats=site_stats
                               , search_form=search_form
                               , search_results=search_results
                               , prod_mode=prod_mode
                               , badge_definitions=badge_definitions)


@app.route('/recipe/<string:recipe_id>', methods=["GET"])
def recipe(recipe_id: str):
    ingredients = get_ingredients(recipe_id)
    print(ingredients)
    nutrition_facts = get_nutrition(recipe_id)
    recipe_instructions = get_instructions(recipe_id)
    recipe_header = get_recipe_header(recipe_id)
    badges = get_badges(recipe_id)
    nav_controls = create_nav_controls(home_button=True, edit_button=True, recipe_button=False, recipe_id=recipe_id)
    return render_template("recipe.html"
                           , recipe_id=recipe_id
                           , ingredients=ingredients
                           , nutrition_facts=nutrition_facts
                           , recipe_instructions=recipe_instructions
                           , recipe_header=recipe_header
                           , badges=badges
                           , nav_controls=nav_controls)


@app.route('/edit_header/<string:recipe_id>', methods=["GET", "POST"])
def edit_header(recipe_id: str = NEW_RECORD_PAGE_INDEX):
    print(f"{request.method} method request for edit_header called with recipe_id: {recipe_id}")
    if 'banner_message' in request.args:  # optional arg
        banner_message = request.args['banner_message']
    else:
        banner_message = ' '

    if request.method == 'POST':
        # commit those changes to the Database, if applicable overwrite recipe_id with newly generated value
        recipe_id = process_header_form(request.form)
        # redirect to new route for newly generated ID
        if recipe_id == '0':
            banner_message = 'New Recipe saved!'
        else:
            banner_message = "Change saved!"
        return redirect(url_for('edit_header', recipe_id=recipe_id, banner_message=banner_message))

    if request.method == 'GET':
        recipe_header_list = get_recipe_header(recipe_id)
        recipe_header = None
        if recipe_id != NEW_RECORD_PAGE_INDEX:
            recipe_header = recipe_header_list[0]
        # recipe edit form
        form = configure_header_form(recipe_id, recipe_header)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id)
        return render_template("edit_header.html"
                               , recipe_id=recipe_id
                               , recipe_header=recipe_header
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/edit_instructions/<string:recipe_id>', methods=["GET", "POST"])
def edit_instructions(recipe_id: str = NEW_RECORD_PAGE_INDEX):
    instruction_id = request.args['instruction_id']
    if 'banner_message' in request.args:  # optional arg
        banner_message = request.args['banner_message']
    else:
        banner_message = ' '
    print(f"{request.method} method request for edit_instructions called with recipe_id: {recipe_id} "
          f"and instruction_id: {instruction_id}")
    if request.method == 'POST':
        # commit those changes to the Database, if applicable overwrite recipe_id with newly generated value
        process_instruction_form(request.form)
        if instruction_id == NEW_RECORD_PAGE_INDEX:
            banner_message = 'New Ingredient saved!'
        else:
            banner_message = "Change saved!"

        instruction_id = DEFAULT_EDITOR_PAGE_INDEX  # reset ID to default after saving changes
        # redirect to new route for newly generated ID
        return redirect(url_for('edit_instructions'
                                , recipe_id=recipe_id
                                , instruction_id=instruction_id
                                , banner_message=banner_message))

    if request.method == 'GET':
        recipe_instructions = get_instructions(recipe_id)
        # recipe edit form
        form = configure_instruction_form(recipe_id, instruction_id, recipe_instructions)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id)
        return render_template("edit_instructions.html"
                               , recipe_id=recipe_id
                               , instruction_id=instruction_id
                               , recipe_instructions=recipe_instructions
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/edit_nutrition/<string:recipe_id>', methods=["GET", "POST"])
def edit_nutrition(recipe_id: str = NEW_RECORD_PAGE_INDEX):
    if 'banner_message' in request.args:     # optional arg
        banner_message = request.args['banner_message']
    else:
        banner_message = ' '
    nutrition_id = request.args['nutrition_id']
    print(f"{request.method} method request for edit_nutrition called with recipe_id: {recipe_id} "
          f"and nutrition_id: {nutrition_id}")
    if request.method == 'POST':
        # commit those changes to the Database, if applicable overwrite recipe_id with newly generated value
        process_nutrition_form(request.form)
        if nutrition_id == NEW_RECORD_PAGE_INDEX:
            banner_message = 'New Nutrition Fact saved!'
        else:
            banner_message = "Change saved!"
        nutrition_id = DEFAULT_EDITOR_PAGE_INDEX   # reset ID to default after saving changes
        # redirect to new route for newly generated ID
        return redirect(url_for('edit_nutrition'
                                , recipe_id=recipe_id
                                , nutrition_id=nutrition_id
                                , banner_message=banner_message))
    if request.method == 'GET':
        nutrition_facts = get_nutrition(recipe_id)
        # recipe edit form
        form = configure_nutrition_form(recipe_id, nutrition_id, nutrition_facts)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id)
        return render_template("edit_nutrition.html"
                               , recipe_id=recipe_id
                               , nutrition_id=nutrition_id
                               , nutrition_facts=nutrition_facts
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/edit_ingredient/<string:recipe_id>', methods=["GET", "POST"])
def edit_ingredients(recipe_id: str = NEW_RECORD_PAGE_INDEX):
    if 'banner_message' in request.args:     # optional arg
        banner_message = request.args['banner_message']
    else:
        banner_message = ' '
    ingredient_id = request.args['ingredient_id']
    print(f"{request.method} method request for edit_nutrition called with recipe_id: {recipe_id} "
          f"and ingredient_id: {ingredient_id}")
    if request.method == 'POST':
        # commit those changes to the Database, if applicable overwrite recipe_id with newly generated value
        process_ingredient_form(request.form)
        if ingredient_id == NEW_RECORD_PAGE_INDEX:
            banner_message = 'New Ingredient saved!'
        else:
            banner_message = "Change saved!"
        ingredient_id = DEFAULT_EDITOR_PAGE_INDEX   # reset ID to default after saving changes
        # redirect to new route for newly generated ID
        return redirect(url_for('edit_ingredients'
                                , recipe_id=recipe_id
                                , ingredient_id=ingredient_id
                                , banner_message=banner_message))
    if request.method == 'GET':
        ingredients = get_ingredients(recipe_id)
        # recipe edit form
        form = configure_ingredient_form(recipe_id, ingredient_id)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id)
        return render_template("edit_ingredients.html"
                               , recipe_id=recipe_id
                               , ingredient_id=ingredient_id
                               , ingredients=ingredients
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/database', methods=["GET", "POST"])
def database():
    form = recipe_forms.DatabaseForm()
    results = ""
    if request.method == 'POST':
        results = process_database_form(request.form)
    form["response"].data = results
    nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=False, recipe_id=None)
    return render_template("database.html", results=results, form=form, nav_controls=nav_controls)


@app.route('/email_recipe', methods=["GET", "POST"])
def email_recipe():
    form = recipe_forms.EmailRecipeForm()
    message = ""
    if request.method == 'POST':
        process_email_form(form)
        message = "Email sent. \n Thank you for the contribution!"
    nav_controls = create_nav_controls(home_button=True)
    return render_template("email_recipe.html", message=message, form=form, nav_controls=nav_controls)


# -------------------- RUN -------------------- #
if __name__ == '__main__':
    app.run(debug=not prod_mode)    # set to False for web deployment, True for local dev

