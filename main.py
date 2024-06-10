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
    , RecipeSearchForm, RecipeTagForm
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
# TODO set to true for prod!!
prod_mode = True   # master toggle to switch between DEV and PROD modes

# create a lookup table for ElementID by NutritionNameID
nutrition_units_by_name_id = {"1": 1, "2": 2, "3": 2, "4": 3, "5": 2, "6": 2, "7": 2, "8": 3, "9": 2}


# -------------------- DB METHODS -------------------- #
def get_tags(recipe_id: int):
    query_string = "SELECT CBTag.TagID, TagName " \
                   "FROM CBTag " \
                   "JOIN CBTagName ON CBTag.TagID = CBTagName.TagID " \
                   "WHERE RecipeID = ? " \
                   "ORDER BY TagName "
    query_args = (recipe_id,)
    return execute_query(query_string, query_args)


def get_ingredients(recipe_id: str):
    query_string = "SELECT IngredientName, CBIngredientPrep.ShortName as Prep, Quantity" \
                   ", CBIngredientName.RecipeID as RelatedRecipeID " \
                   ", CBIngredientUnit.ShortName as Units, IngredientID, FootNote " \
                   "FROM CBIngredient " \
                   "JOIN CBIngredientName ON CBIngredient.IngredientNameID = CBIngredientName.IngredientNameID " \
                   "JOIN CBIngredientPrep ON CBIngredientPrep.PrepID = CBIngredient.PrepID " \
                   "JOIN CBIngredientUnit ON CBIngredientUnit.IngredientUnitID = CBIngredient.IngredientUnitID " \
                   "WHERE CBIngredient.RecipeID = ? " \
                   "ORDER BY IngredientName"
    query_args = (recipe_id,)
    return execute_query(query_string, query_args)


def get_nutrition(recipe_id: str):
    query_string = "SELECT CBElementName.ShortName as ElementName, CBElementName.ElementNameID as ElementNameCode" \
                   ", NutritionValue, CBElementUnit.ShortName as Units, CBElementUnit.ElementUnitID as UnitsCode" \
                   ", NutritionID " \
                   "FROM CBNutrition Element " \
                   "JOIN CBElementName ON CBElementName.ElementNameID = Element.ElementNameID " \
                   "JOIN CBElementUnit ON CBElementUnit.ElementUnitID = Element.ElementUnitID " \
                   "WHERE Element.RecipeID = ?"
    query_args = (recipe_id,)
    return execute_query(query_string, query_args)


def get_instructions(recipe_id: str):
    query_string = "SELECT StepNumber, StepText, InstructionID " \
                   "FROM CBInstructions " \
                   f"WHERE RecipeID = ? " \
                   "ORDER BY RecipeID ASC, StepNumber ASC"
    query_args = (recipe_id,)
    return execute_query(query_string, query_args)


def get_recipe_header(recipe_id: str):
    query_string = "SELECT RecipeName, CookingTime, Servings, Source, CreationGMT, RecipeTypeID, PhotoURL " \
                   "FROM CBRecipe " \
                   f"WHERE RecipeID = ? "
    query_args = (recipe_id,)
    header = execute_query(query_string, query_args)
    return header


def get_badges(recipe_id: str):
    query_string = "SELECT BadgeName, BadgeIconAddress " \
                   "FROM CBBadge " \
                   "JOIN CBRecipeBadge ON CBRecipeBadge.BadgeID = CBBadge.BadgeID " \
                   f"WHERE RecipeID = ? "
    query_args = (recipe_id,)
    return execute_query(query_string, query_args)


def get_recent_recipes():
    query_string = "SELECT RecipeID " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeType ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "ORDER BY CreationGMT DESC " \
                   "LIMIT 10 "
    query_args = ()
    return get_card_data(query_string, query_args)


def get_recipes_by_tag(tag_name: str):
    query_string = "SELECT DISTINCT CBRecipe.RecipeID " \
                   "FROM CBRecipe " \
                   "JOIN CBTag ON CBTag.RecipeID = CBRecipe.RecipeID " \
                   "JOIN CBTagName ON CBTagName.TagID = CBTag.TagID " \
                   "WHERE TagName = ? "
    query_args = (tag_name, )
    return get_card_data(query_string, query_args)


def get_recipes_by_badge(badge_name: str):
    query_string = "SELECT DISTINCT CBRecipe.RecipeID " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeBadge ON CBRecipeBadge.RecipeID = CBRecipe.RecipeID " \
                   "JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID " \
                   "WHERE BadgeName = ? "
    query_args = (badge_name, )
    return get_card_data(query_string, query_args)


def get_recipes_by_category(category: str):
    query_string = "SELECT RecipeID " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeType ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "WHERE CBRecipeType.LongName = ? "
    query_args = (category, )
    return get_card_data(query_string, query_args)


def get_category_cards():
    query_string = "SELECT CBRecipeType.LongName CategoryName, PhotoUrl, COUNT(*) RecipeCount " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeType ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "GROUP BY CBRecipeType.LongName " \
                   "HAVING CreationGMT = MAX(CreationGMT) "
    query_args = ()
    return execute_query(query_string, query_args)


def get_site_stats():
    query_string = "SELECT CBRecipeType.LongName 'Category', COUNT(*) 'Count', 1 " \
                   "FROM CBRecipeType " \
                   "JOIN CBRecipe ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "GROUP BY CBRecipeType.LongName " \
                   "UNION SELECT 'TOTAL', COUNT(*), 0 " \
                   "FROM CBRecipe " \
                   "ORDER BY 3 DESC, 1 ASC"
    query_args = ()
    return execute_query(query_string, query_args)


def get_next_recipe_id(recipe_id):
    query_string = "SELECT MAX(Result) AS RecipeID FROM (" \
                   "SELECT COALESCE(MIN(RecipeID), -1) Result FROM CBRecipe WHERE RecipeID > ? " \
                   "UNION SELECT MIN(RecipeID) Result FROM CBRecipe)"
    query_args = (recipe_id, )
    next_id = execute_query(query_string, query_args)
    return next_id[0]["RecipeID"]


def get_database_map():
    table_column_pairs = {}
    query_string = "SELECT Name as TableName " \
                   "FROM SQLite_Master " \
                   "WHERE Type = 'table' " \
                   "AND Name != 'sqlite_sequence' " \
                   "ORDER BY 1"
    query_args = ()
    table_names = execute_query(query_string, query_args)
    for table in table_names:
        query_string = "SELECT Name as ColumnName " \
                       "FROM PRAGMA_TABLE_INFO(?) " \
                       "ORDER BY 1"
        query_args = (table["TableName"], )
        table_columns = execute_query(query_string, query_args)
        print(table["TableName"])
        table_column_pairs[table["TableName"]] = table_columns
        print(table_column_pairs)
    return table_column_pairs


def get_card_data(recipe_id_query: str, query_args: tuple):
    query_string = "WITH Recipes AS (" \
                   f"{recipe_id_query}" \
                   "), Badges AS (" \
                   "SELECT Recipes.RecipeID, GROUP_CONCAT(BadgeName, ', ') BadgeList " \
                   "FROM Recipes " \
                   "JOIN CBRecipeBadge ON CBRecipeBadge.RecipeID = Recipes.RecipeID " \
                   "JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID " \
                   "GROUP BY Recipes.RecipeID " \
                   "), Tags AS (" \
                   "SELECT Recipes.RecipeID, GROUP_CONCAT(TagName, ', ') TagList " \
                   "FROM Recipes " \
                   "JOIN CBTag ON CBTag.RecipeID = Recipes.RecipeID " \
                   "JOIN CBTagName ON CBTagName.TagID = CBTag.TagID " \
                   "GROUP BY Recipes.RecipeID " \
                   ")" \
                   "SELECT Recipes.RecipeID " \
                   ", RecipeName " \
                   ", PhotoURL " \
                   ", RecipeTypeID " \
                   ", CookingTime " \
                   ", TagList " \
                   ", BadgeList " \
                   "FROM Recipes " \
                   "JOIN CBRecipe ON CBRecipe.RecipeID = Recipes.RecipeID " \
                   "LEFT JOIN Tags ON Tags.RecipeID = Recipes.RecipeID " \
                   "LEFT JOIN Badges ON Badges.RecipeID = Recipes.RecipeID " \
                   "ORDER BY 2"
    search_results = execute_query(query_string, query_args)
    for result in search_results:
        if result["PhotoURL"] is None:
            result["PhotoURL"] = get_default_photo_by_recipe_type(result["RecipeTypeID"])
    return search_results


def update_header(recipe_id: str, new_recipe_name: str, new_recipe_time: int
                  , new_recipe_servings: int, new_recipe_source: str, recipe_type_id: int):
    update_script = "UPDATE CBRecipe " \
                    'SET RecipeName = ?' \
                    ', CookingTime = ?' \
                    ', Servings = ?' \
                    ', Source = ? ' \
                    ', RecipeTypeID = ? ' \
                    'WHERE RecipeID = ?'
    query_args = (new_recipe_name, new_recipe_time, new_recipe_servings, new_recipe_source, recipe_type_id, recipe_id)
    execute_update_script(update_script, query_args)


def update_instruction(instruction_id: str, new_instruction: str):
    update_script = "UPDATE CBInstructions " \
                    'SET StepText = ? ' \
                    'WHERE InstructionID = ?'
    query_args = (new_instruction, instruction_id)
    execute_update_script(update_script, query_args)


def update_nutrition(recipe_id: str, nutrition_id: str, new_nutrition_name_code: str, new_nutrition_value: float
                     , new_nutrition_unit_code: str):
    update_script = "UPDATE CBNutrition " \
                    'SET ElementNameID = ?' \
                    ', NutritionValue = ?' \
                    ', ElementUnitID = ? ' \
                    'WHERE NutritionID = ?'
    query_args = (new_nutrition_name_code, new_nutrition_value, new_nutrition_unit_code, nutrition_id)
    execute_update_script(update_script, query_args)


def update_ingredient(ingredient_id: str, new_ingredient_name_id: str, new_quantity: float
                      , new_prep_id: str, new_unit_id: str):
    update_script = "UPDATE CBIngredient " \
                    'SET IngredientNameID = ?' \
                    ', Quantity = ?' \
                    ', PrepID = ?' \
                    ', IngredientUnitID = ? ' \
                    'WHERE IngredientID = ?'
    query_args = (new_ingredient_name_id, new_quantity, new_prep_id, new_unit_id, ingredient_id)
    execute_update_script(update_script, query_args)


def update_badges(recipe_id: int):
    query_string = "SELECT RecipeTypeID " \
                   "FROM CBRecipe " \
                   "WHERE RecipeID = ? "
    query_args = (recipe_id,)
    recipe_type = execute_query(query_string, query_args)[0]["RecipeTypeID"]
    # only process badge changes on recipe types which allow it
    if recipe_type == 3 or recipe_type == 9:
        query_string = "SELECT CookingTime" \
                       ", COALESCE(Max(Veg.IsVegetarian), 'Y') Vegetarian" \
                       ", COALESCE(Calories.NutritionValue, 9000) Calories" \
                       ", COALESCE(Fat.NutritionValue, 9000) Fat " \
                       "FROM CBRecipe " \
                       "LEFT JOIN CBIngredient ON CBIngredient.RecipeID = CBRecipe.RecipeID " \
                       "LEFT JOIN CBIngredientName Veg ON Veg.IngredientNameID = CBIngredient.IngredientNameID " \
                       "LEFT JOIN CBNutrition Calories ON Calories.RecipeID = CBRecipe.RecipeID " \
                       "AND Calories.ElementNameID = 1 " \
                       "LEFT JOIN CBNutrition Fat ON Fat.RecipeID = CBRecipe.RecipeID " \
                       "AND Fat.ElementNameID = 9 " \
                       "WHERE CBRecipe.RecipeID = ? "
        query_args = (recipe_id,)
        badge_stats = execute_query(query_string, query_args)[0]
        # process changes to badges
        if float(badge_stats["Fat"]) <= float(LOW_FAT_MEAL_THRESHOLD):
            # add low-fat badge, if not already present
            badge_name = "Low Fat"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            'SELECT ?, BadgeID ' \
                            'FROM CBBadge ' \
                            'WHERE BadgeName = ? ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            'AND BadgeName = ? ' \
                            'WHERE RecipeID = ?) ' \
                            '= 0'
            query_args = (recipe_id, badge_name, badge_name, recipe_id)
            execute_insert_script(insert_script, query_args)
        else:   # above fat threshold
            delete_script = 'DELETE FROM CBRecipeBadge ' \
                            'WHERE RecipeID = ? AND BadgeID = 3'  # low fat badge ID
            query_args = (recipe_id, )
            execute_delete_script(delete_script, query_args)
        if float(badge_stats["Calories"]) <= float(LOW_CAL_THRESHOLD):
            # add low-cal badge, if not already present
            badge_name = "Low Calorie"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            'SELECT ?, BadgeID ' \
                            'FROM CBBadge ' \
                            'WHERE BadgeName = ? ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            'AND BadgeName = ? ' \
                            'WHERE RecipeID = ?) ' \
                            '= 0'
            query_args = (recipe_id, badge_name, badge_name, recipe_id)
            execute_insert_script(insert_script, query_args)
        else:   # above calorie threshold
            delete_script = 'DELETE FROM CBRecipeBadge ' \
                            'WHERE RecipeID = ? AND BadgeID = 2'  # low cal badge ID
            query_args = (recipe_id, )
            execute_delete_script(delete_script, query_args)
        if int(badge_stats["CookingTime"]) <= QUICK_MEAL_THRESHOLD:
            badge_name = "Quick Prep"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            'SELECT ?, BadgeID ' \
                            'FROM CBBadge ' \
                            'WHERE BadgeName = ? ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            'AND BadgeName = ? ' \
                            'WHERE RecipeID = ?) ' \
                            '= 0'
            query_args = (recipe_id, badge_name, badge_name, recipe_id)
            execute_insert_script(insert_script, query_args)
        else:
            delete_script = 'DELETE FROM CBRecipeBadge ' \
                            'WHERE RecipeID = ? AND BadgeID = 1'
            query_args = (recipe_id, )
            execute_delete_script(delete_script, query_args)
        if badge_stats["Vegetarian"] == 'Y':
            badge_name = "Vegetarian"
            insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                            'SELECT ?, BadgeID ' \
                            'FROM CBBadge ' \
                            'WHERE BadgeName = ? ' \
                            'AND (SELECT Count(*) FROM CBRecipeBadge ' \
                            'JOIN CBBadge ON CBBadge.BadgeID = CBRecipeBadge.BadgeID ' \
                            'AND BadgeName = ? ' \
                            'WHERE RecipeID = ?) ' \
                            '= 0'
            query_args = (recipe_id, badge_name, badge_name, recipe_id)
            execute_insert_script(insert_script, query_args)
        else:
            badge_id_veggie = 4
            delete_script = "DELETE " \
                            "FROM CBRecipeBadge " \
                            "WHERE RecipeID = ? AND BadgeID = ? "
            query_args = (recipe_id, badge_id_veggie)
            execute_delete_script(delete_script, query_args)


def create_header(new_recipe_name: str, new_recipe_time: int
                  , new_recipe_servings: int, new_recipe_source: str, new_creationGMT: str, recipe_type_id: str):
    # inserts a new record into the header table, brings back the new ID.
    insert_script = 'INSERT INTO CBRecipe(RecipeName, CookingTime, Servings, Source, CreationGMT, RecipeTypeID)' \
                    'SELECT ?, ?, ?, ?, ?, ? '
    query_args = (new_recipe_name, new_recipe_time, new_recipe_servings
                  , new_recipe_source, new_creationGMT, recipe_type_id)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBRecipe', id_column='RecipeID')

    # now add badge based on cook time, if applicable
    if int(new_recipe_time) <= QUICK_MEAL_THRESHOLD:
        insert_script = 'INSERT INTO CBRecipeBadge (RecipeID, BadgeID) ' \
                        'SELECT ?, 1'
        query_args = (new_id, )
        execute_insert_script(insert_script, query_args)

    # assume all recipes are vegetarian off the bat. only toggle to No when an ingredient is added which is not.
    badge_id_veggie = 4
    insert_script = "INSERT INTO CBRecipeBadge (RecipeID, BadgeID) SELECT ?, ?"
    query_args = (new_id, badge_id_veggie)
    execute_insert_script(insert_script, query_args)

    return new_id


def create_instruction(recipe_id: str, new_instruction: str):
    # query for max instruction step number
    query_string = "SELECT MAX(StepNumber) as MaxStep " \
                   "FROM CBInstructions " \
                   "WHERE RecipeID = ? "
    query_args = (recipe_id, )
    max_step = execute_query(query_string, query_args)[0]["MaxStep"]
    if max_step is None:
        max_step = 0
    # increment
    new_step_number = int(max_step) + 1
    # insert
    insert_script = 'INSERT INTO CBInstructions(RecipeID, StepNumber, StepText) ' \
                    'SELECT ?, ?, ? '
    query_args = (recipe_id, new_step_number, new_instruction)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBInstructions', id_column='InstructionID')
    return new_id


def create_nutrition(recipe_id: str, new_nutrition_name_code: str, new_nutrition_value: float
                     , new_nutrition_unit_code: str):
    # inserts a new record into the header table, brings back the new ID.
    insert_script = 'INSERT INTO CBNutrition(RecipeID, ElementNameID, NutritionValue, ElementUnitID)' \
                    'SELECT ?, ?, ?, ? '
    query_args = (recipe_id, new_nutrition_name_code, new_nutrition_value, new_nutrition_unit_code)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBNutrition', id_column='NutritionID')
    return new_id


def create_ingredient_name(ingredient_name: str, is_vegetarian: str, search_name: str, linked_recipe: int):
    insert_script = 'INSERT INTO CBIngredientName(IngredientName, IsVegetarian, SearchName, RecipeID) ' \
                    'SELECT ?, ?, ? ' \
                    ', IIF(CAST(? AS INTEGER) == -1, NULL, ?) '
    query_args = (ingredient_name, is_vegetarian, search_name, linked_recipe, linked_recipe)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBIngredientName', id_column='IngredientNameID')
    return new_id


def create_ingredient_prep(ingredient_prep: str):
    insert_script = 'INSERT INTO CBIngredientPrep(ShortName, LongName) ' \
                    'SELECT ?, ? '
    query_args = (ingredient_prep, ingredient_prep)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBIngredientPrep', id_column='PrepID')
    return new_id


def create_ingredient_unit(ingredient_unit: str):
    insert_script = 'INSERT INTO CBIngredientUnit(ShortName, LongName) ' \
                    'SELECT ?, ? '
    query_args = (ingredient_unit, ingredient_unit)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBIngredientUnit', id_column='IngredientUnitID')
    return new_id


def create_ingredient(recipe_id: str, ingredient_name_id: str, quantity: str, prep_id: str, ingredient_unit_id: str):
    insert_script = 'INSERT INTO CBIngredient(RecipeID, IngredientNameID, Quantity, PrepID, IngredientUnitID) ' \
                    'SELECT ?, ?, ?, ?, ? '
    query_args = (recipe_id, ingredient_name_id, quantity, prep_id, ingredient_unit_id)
    new_id = execute_insert_script(insert_script, query_args=query_args
                                   , table_name='CBIngredient', id_column='IngredientID')
    return new_id


def create_tag(recipe_id: int, tag_name_code: int, tag_name_new: str):
    print(f"new tag name: {tag_name_new} has length {len(tag_name_new)}")
    if len(tag_name_new) > 0:
        # create new tag name
        insert_script = 'INSERT INTO CBTagName (TagName) ' \
                        'SELECT ? '
        query_args = (tag_name_new, )
        tag_name_code = execute_insert_script(insert_script, query_args=query_args
                                              , table_name='CBTagName', id_column='TagID')

    # insert a link connecting the specified tag to the specified recipe
    insert_script = 'INSERT INTO CBTag (RecipeID, TagID) ' \
                    'SELECT ?, ? '
    query_args = (recipe_id, tag_name_code)
    execute_insert_script(insert_script, query_args=query_args)


def delete_recipe_ingredient(ingredient_id: str):
    delete_script = 'DELETE FROM CBIngredient WHERE IngredientID = ? '
    query_args = (ingredient_id,)
    execute_delete_script(delete_script, query_args)


def delete_recipe_nutrition_fact(nutrition_id: str):
    delete_script = 'DELETE FROM CBNutrition WHERE NutritionID = ? '
    query_args = (nutrition_id,)
    execute_delete_script(delete_script, query_args)


def delete_recipe_instruction(instruction_id: str):
    delete_script = 'DELETE FROM CBInstructions WHERE InstructionID = ? '
    query_args = (instruction_id,)
    execute_delete_script(delete_script, query_args)


def delete_recipe_tag(recipe_id: int, tag_id: int):
    delete_script = 'DELETE FROM CBTag WHERE RecipeID = ? AND TagID = ? '
    query_args = (recipe_id, tag_id)
    execute_delete_script(delete_script, query_args)


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
    if nutrition_id == DEFAULT_EDITOR_PAGE_INDEX:
        # default page (no editing)
        form.nutrition_name.data = nutrition_name_code
        form.nutrition_value.data = nutrition_value
    elif nutrition_id == NEW_RECORD_PAGE_INDEX:
        # Add new element page
        form.nutrition_name.data = nutrition_name_code
        form.nutrition_value.data = nutrition_value
    else:
        # get the current data associated with this ID
        for fact in nutrition_facts:
            if str(fact['NutritionID']) == nutrition_id:
                nutrition_name_code = fact['ElementNameCode']
                nutrition_value = fact['NutritionValue']
                break
        query_string = "SELECT ElementNameID, LongName FROM CBElementName ORDER BY 2 ASC"
        query_args = ()
        nutrition_element_names = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        form.nutrition_name.choices = nutrition_element_names
        form.nutrition_name.data = str(nutrition_name_code)
        form.nutrition_value.data = nutrition_value
    form.recipe_id.data = recipe_id
    form.nutrition_id.data = nutrition_id
    return form


def configure_tags_form(recipe_id: int):
    form = RecipeTagForm()
    form.recipe_id.data = recipe_id
    # pull the latest list of names
    query_string = "SELECT TagID, TagName FROM CBTagName ORDER BY 2 ASC"
    query_args = ()
    form.tag_name.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
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
        query_args = ()
        form.ingredient_name.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        form.is_vegetarian.data = 'y'  # most ingredients are vegetarian, so default to yes
        form.search_name.process_data("Not Searchable")
        form.ingredient_prep_new.data = None
        form.ingredient_prep.data = default_combo_value
        query_string = "SELECT PrepID, LongName FROM CBIngredientPrep ORDER BY 2 ASC"
        query_args = ()
        form.ingredient_prep.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        form.ingredient_prep.process_data(1)    # default value which corresponds to 'None'
        form.ingredient_unit_new.data = None
        form.ingredient_unit.data = default_combo_value
        query_string = "SELECT IngredientUnitID, LongName FROM CBIngredientUnit ORDER BY 2 ASC"
        query_args = ()
        form.ingredient_unit.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        query_string = "SELECT -1, '' UNION SELECT RecipeID, RecipeName FROM CBRecipe ORDER BY 2 ASC"
        query_args = ()
        form.linked_recipe.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)

        form.ingredient_quantity.data = default_quantity

    else:
        # Edit existing record
        # get the current data associated with this ID
        query_string = "SELECT IngredientNameID, IngredientUnitID, PrepID, Quantity " \
                "FROM CBIngredient " \
                "WHERE IngredientID = ? "
        query_args = (ingredient_id, )
        ingredient_data = execute_query(query_string, query_args)
        form.ingredient_name_new.data = None
        query_string = "SELECT IngredientNameID, IngredientName FROM CBIngredientName ORDER BY 2 ASC"
        query_args = ()
        form.ingredient_name.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        form.ingredient_name.process_data(int(ingredient_data[0]["IngredientNameID"]))

        form.ingredient_prep_new.data = None
        query_string = "SELECT PrepID, LongName FROM CBIngredientPrep ORDER BY 2 ASC"
        query_args = ()
        form.ingredient_prep.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        form.ingredient_prep.process_data(int(ingredient_data[0]["PrepID"]))

        form.ingredient_unit_new.data = None
        query_string = "SELECT IngredientUnitID, LongName FROM CBIngredientUnit ORDER BY 2 ASC"
        query_args = ()
        form.ingredient_unit.choices = execute_query(query_string, query_args=query_args, convert_to_dict=False)
        form.ingredient_unit.process_data(int(ingredient_data[0]["IngredientUnitID"]))

        form.ingredient_quantity.data = ingredient_data[0]["Quantity"]

    return form


def configure_search_form():
    form = RecipeSearchForm()
    if form.recipe_type.data is None:
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
    nutrition_unit_code = nutrition_units_by_name_id[nutrition_name_code]
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


def process_tag_form(form):
    print("processing tag form: ")
    # pull data from the form
    tag_name_code = form["tag_name"]
    tag_name_new = form["tag_name_new"]
    recipe_id = form["recipe_id"]
    # add new record
    nutrition_id = create_tag(recipe_id=recipe_id, tag_name_code=tag_name_code, tag_name_new=tag_name_new)


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
    query_args_optional = ()
    query_args = ()
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
        recipe_type_query_string = "AND CBRecipe.RecipeTypeID = ? "
        query_args_optional = (recipe_type, )

    query_string = "SELECT DISTINCT CBRecipe.RecipeID " \
                   "FROM CBRecipe " \
                   "JOIN CBRecipeType ON CBRecipe.RecipeTypeID = CBRecipeType.RecipeTypeID " \
                   "JOIN CBIngredient ON CBRecipe.RecipeID = CBIngredient.RecipeID " \
                   "JOIN CBIngredientName ON CBIngredient.IngredientNameID = CBIngredientName.IngredientNameID " \
                   "AND CBIngredientName.SearchName LIKE ? " + badge_query_string + \
                   "LEFT JOIN CBTag ON CBTag.RecipeID = CBRecipe.RecipeID " \
                   "LEFT JOIN CBTagName ON CBTag.TagID = CBTagName.TagID " \
                   "WHERE (RecipeName LIKE ? OR TagName LIKE ? ) " \
                   f"{recipe_type_query_string}"
    query_args = (ingredient_search_name, search_keyword, search_keyword) + query_args_optional
    return get_card_data(query_string, query_args)


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
def create_nav_controls(home_button: bool = False, recipe_button: bool = False, recipe_id: int = 0
                        , edit_button: bool = False, search_button: bool = True, next_recipe: bool = False
                        , next_recipe_id: int = 0):
    # currently simple converts the inputs into a JSON / Dict which can be read by the nav html
    if prod_mode:
        edit_button = False  # edit button never allowed in prod mode
        next_recipe = False
    return {
        "home": home_button
        , "edit": edit_button
        , "recipe": recipe_button
        , "recipeID": recipe_id
        , "search": search_button
        , "next_recipe": next_recipe
        , "next_recipe_id": next_recipe_id
    }


def get_badge_definitions():
    definitions = [
        f"Low Fat: <= {LOW_FAT_MEAL_THRESHOLD}g Sat Fat,   Low Cal: <= {LOW_CAL_THRESHOLD}cal,"
        , f"Quick Meal: <= {QUICK_MEAL_THRESHOLD}min total prep & cook time"
    ]
    return definitions


def get_default_photo_by_recipe_type(recipe_type_code: int):
    if recipe_type_code == 1:   # dinner
        photo_location = '../static/assets/img/dinner.png'
    elif recipe_type_code == 3:   # spice blend
        photo_location = '../static/assets/img/spice.png'
    elif recipe_type_code == 4:   # drink
        photo_location = '../static/assets/img/drink.png'
    elif recipe_type_code == 7:   # snack
        photo_location = '../static/assets/img/snack.png'
    elif recipe_type_code == 9:   # sauce
        photo_location = '../static/assets/img/sauce.png'
    else:   # other
        photo_location = '../static/assets/img/other.png'
    return photo_location


# -------------------- APP ROUTES -------------------- #
@app.route('/', methods=["GET"])
def home():
    print(f"{request.method} method request for home called")
    # get data for recent recipe widget
    site_stats = get_site_stats()
    category_cards = get_category_cards()
    recent_recipes = get_recent_recipes()
    badge_definitions = get_badge_definitions()
    nav_controls = create_nav_controls(home_button=False, edit_button=False, recipe_button=False, search_button=True)
    return render_template("index.html"
                           , search_results=recent_recipes
                           , site_stats=site_stats
                           , prod_mode=prod_mode
                           , nav_controls=nav_controls
                           , badge_definitions=badge_definitions
                           , category_cards=category_cards)


@app.route('/recipe/<string:recipe_id>', methods=["GET"])
def recipe(recipe_id: int):
    print(f"{request.method} method request for recipe called with recipe_id: {recipe_id}")
    ingredients = get_ingredients(recipe_id)
    nutrition_facts = get_nutrition(recipe_id)
    recipe_instructions = get_instructions(recipe_id)
    recipe_header = get_recipe_header(recipe_id)[0]
    if recipe_header['PhotoURL'] is None:
        recipe_header['PhotoURL'] = get_default_photo_by_recipe_type(recipe_header['RecipeTypeID'])
    badges = get_badges(recipe_id)
    tags = get_tags(recipe_id)
    next_recipe_id = get_next_recipe_id(recipe_id)
    nav_controls = create_nav_controls(home_button=True, edit_button=True, recipe_button=False, recipe_id=recipe_id
                                       , search_button=True, next_recipe=True, next_recipe_id=next_recipe_id)
    return render_template("recipe.html"
                           , recipe_id=recipe_id
                           , ingredients=ingredients
                           , nutrition_facts=nutrition_facts
                           , recipe_instructions=recipe_instructions
                           , recipe_header=recipe_header
                           , badges=badges
                           , tags=tags
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
        update_badges(recipe_id)
        return redirect(url_for('edit_header', recipe_id=recipe_id, banner_message=banner_message))

    if request.method == 'GET':
        recipe_header_list = get_recipe_header(recipe_id)
        recipe_header = None
        if recipe_id != NEW_RECORD_PAGE_INDEX:
            recipe_header = recipe_header_list[0]
        # recipe edit form
        form = configure_header_form(recipe_id, recipe_header)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id
                                           , search_button=True)
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
            banner_message = 'New Instruction saved!'
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
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id
                                           , search_button=True)
        return render_template("edit_instructions.html"
                               , recipe_id=recipe_id
                               , instruction_id=instruction_id
                               , recipe_instructions=recipe_instructions
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/delete_instruction/<string:recipe_id>', methods=["GET"])
def delete_instruction(recipe_id: str):
    instruction_id = request.args['instruction_id']
    print(f"{request.method} method request for delete_instruction called with recipe_id: {recipe_id} "
          f"and ingredient_id: {instruction_id}")
    delete_recipe_instruction(instruction_id)
    return redirect(url_for('edit_instructions', recipe_id=recipe_id, instruction_id=DEFAULT_EDITOR_PAGE_INDEX))


@app.route('/edit_nutrition/<string:recipe_id>', methods=["GET", "POST"])
def edit_nutrition(recipe_id: int = NEW_RECORD_PAGE_INDEX):
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
        update_badges(recipe_id)
        # redirect to new route for newly generated ID
        return redirect(url_for('edit_nutrition'
                                , recipe_id=recipe_id
                                , nutrition_id=nutrition_id
                                , banner_message=banner_message))
    if request.method == 'GET':
        nutrition_facts = get_nutrition(recipe_id)
        # recipe edit form
        form = configure_nutrition_form(recipe_id, nutrition_id, nutrition_facts)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id
                                           , search_button=True)
        return render_template("edit_nutrition.html"
                               , recipe_id=recipe_id
                               , nutrition_id=nutrition_id
                               , nutrition_facts=nutrition_facts
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/delete_nutrition/<string:recipe_id>', methods=["GET"])
def delete_nutrition(recipe_id: str):
    nutrition_id = request.args['nutrition_id']
    print(f"{request.method} method request for delete_nutrition called with recipe_id: {recipe_id} "
          f"and ingredient_id: {nutrition_id}")
    delete_recipe_nutrition_fact(nutrition_id)
    update_badges(recipe_id)
    return redirect(url_for('edit_nutrition', recipe_id=recipe_id, nutrition_id=DEFAULT_EDITOR_PAGE_INDEX))


@app.route('/edit_ingredient/<string:recipe_id>', methods=["GET", "POST"])
def edit_ingredients(recipe_id: str = NEW_RECORD_PAGE_INDEX):
    if 'banner_message' in request.args:     # optional arg
        banner_message = request.args['banner_message']
    else:
        banner_message = ' '
    ingredient_id = request.args['ingredient_id']
    print(f"{request.method} method request for edit_ingredients called with recipe_id: {recipe_id} "
          f"and ingredient_id: {ingredient_id}")
    if request.method == 'POST':
        # commit those changes to the Database, if applicable overwrite recipe_id with newly generated value
        process_ingredient_form(request.form)
        if ingredient_id == NEW_RECORD_PAGE_INDEX:
            banner_message = 'New Ingredient saved!'
        else:
            banner_message = "Change saved!"
        ingredient_id = DEFAULT_EDITOR_PAGE_INDEX   # reset ID to default after saving changes
        update_badges(recipe_id)
        # redirect to new route for newly generated ID
        return redirect(url_for('edit_ingredients'
                                , recipe_id=recipe_id
                                , ingredient_id=ingredient_id
                                , banner_message=banner_message))
    if request.method == 'GET':
        ingredients = get_ingredients(recipe_id)
        # recipe edit form
        form = configure_ingredient_form(recipe_id, ingredient_id)
        nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=True, recipe_id=recipe_id
                                           , search_button=True)
        return render_template("edit_ingredients.html"
                               , recipe_id=recipe_id
                               , ingredient_id=ingredient_id
                               , ingredients=ingredients
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/delete_ingredient/<string:recipe_id>', methods=["GET"])
def delete_ingredient(recipe_id: str):
    ingredient_id = request.args['ingredient_id']
    print(f"{request.method} method request for delete_ingredient called with recipe_id: {recipe_id} "
          f"and ingredient_id: {ingredient_id}")
    delete_recipe_ingredient(ingredient_id)
    update_badges(recipe_id)
    return redirect(url_for('edit_ingredients', recipe_id=recipe_id, ingredient_id=DEFAULT_EDITOR_PAGE_INDEX))


@app.route('/edit_tags/<string:recipe_id>', methods=["GET", "POST"])
def edit_tags(recipe_id: int = NEW_RECORD_PAGE_INDEX):
    if 'banner_message' in request.args:     # optional arg
        banner_message = request.args['banner_message']
    else:
        banner_message = ' '
    print(f"{request.method} method request for edit_tags called with recipe_id: {recipe_id}")
    if request.method == 'POST':
        process_tag_form(request.form)
        banner_message = 'New Tag saved!'
        tag_id = DEFAULT_EDITOR_PAGE_INDEX   # reset ID to default after saving changes
        # use redirect to make a GET request to the page now that data has been processed
        return redirect(url_for('edit_tags'
                                , recipe_id=recipe_id
                                , banner_message=banner_message))
    if request.method == 'GET':
        tags = get_tags(recipe_id)
        # recipe edit form
        form = configure_tags_form(recipe_id)
        nav_controls = create_nav_controls(home_button=True, edit_button=True, recipe_button=True, recipe_id=recipe_id
                                           , search_button=True)
        return render_template("edit_tags.html"
                               , recipe_id=recipe_id
                               , tags=tags
                               , form=form
                               , banner_message=banner_message
                               , nav_controls=nav_controls)


@app.route('/delete_tag/<string:recipe_id>', methods=["GET"])
def delete_tag(recipe_id: str = NEW_RECORD_PAGE_INDEX):
    tag_id = request.args['tag_id']
    print(f"{request.method} method request for delete_tag called with recipe_id: {recipe_id} "
          f"and tag_id: {tag_id}")
    delete_recipe_tag(recipe_id, tag_id)
    return redirect(url_for('edit_tags', recipe_id=recipe_id, tag_id=DEFAULT_EDITOR_PAGE_INDEX))


@app.route('/database', methods=["GET", "POST"])
def database():
    form = recipe_forms.DatabaseForm()
    results = ""
    if request.method == 'POST':
        results = process_database_form(request.form)
    form["response"].data = results
    database_map = get_database_map()
    nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=False, recipe_id=None
                                       , search_button=True)
    return render_template("database.html", results=results, form=form, nav_controls=nav_controls
                           , database_map=database_map)


@app.route('/email_recipe', methods=["GET", "POST"])
def email_recipe():
    form = recipe_forms.EmailRecipeForm()
    message = ""
    if request.method == 'POST':
        process_email_form(form)
        message = "Email sent. \n Thank you for the contribution!"
    nav_controls = create_nav_controls(home_button=True)
    return render_template("email_recipe.html", message=message, form=form, nav_controls=nav_controls
                           , search_button=True)


@app.route('/search', methods=["GET", "POST"])
def search():
    # collect optional kw args
    if 'tag_name' in request.args:     # optional arg
        tag_name = request.args['tag_name']
    else:
        tag_name = None
    if 'category' in request.args:     # optional arg
        category = request.args['category']
    else:
        category = None
    if 'badge_name' in request.args:     # optional arg
        badge_name = request.args['badge_name']
    else:
        badge_name = None
    print(f"{request.method} method request for search called with tag_name: {tag_name}")
    search_form = configure_search_form()
    message = ""
    search_results = []
    nav_controls = create_nav_controls(home_button=True, edit_button=False, recipe_button=False, search_button=False)
    if request.method == 'POST':
        search_results = process_search_form(request.form)
        if len(search_results) == 0:
            message = "No recipes were found to match your search conditions."
        elif "random" in request.form:
            # if the "pick for me" box was checked, go directly to a random recipe from the results
            result_count = len(search_results)
            index = randrange(result_count)
            return redirect(url_for('recipe', recipe_id=search_results[index]["RecipeID"]))
        return render_template("search_screen.html"
                               , search_form=search_form
                               , search_results=search_results
                               , message=message
                               , nav_controls=nav_controls)
    else:
        if tag_name is not None:
            search_results = get_recipes_by_tag(tag_name)
        elif category is not None:
            search_results = get_recipes_by_category(category)
        elif badge_name is not None:
            search_results = get_recipes_by_badge(badge_name)
        return render_template("search_screen.html"
                               , search_form=search_form
                               , search_results=search_results
                               , message=message
                               , nav_controls=nav_controls)


# -------------------- RUN -------------------- #
if __name__ == '__main__':
    app.run(debug=not prod_mode)    # set to False for web deployment, True for local dev

