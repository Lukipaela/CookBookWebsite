# imports
from wtforms import validators, SubmitField, SelectField, StringField, IntegerField, DecimalField, TextAreaField\
    , BooleanField, SelectMultipleField
from flask_wtf import FlaskForm  # pip install Flask-WTF
from sqlite_handlers import execute_query


# -------------------- FORM DEFINITIONS -------------------- #
class RecipeHeaderForm(FlaskForm):
    recipe_name = StringField(label="Recipe Name", render_kw={"placeholder": "New recipe name"})
    recipe_servings = IntegerField(label="Servings")
    recipe_time = IntegerField(label="Cooking Time")
    recipe_source = StringField(label="Source"
                                , render_kw={"placeholder": "EG. Jimmy Needles or www.JimmyNeedles.com/recipe/1"})
    __query_string = "SELECT RecipeTypeID, ShortName FROM CBRecipeType ORDER BY 2 ASC"
    __recipe_type_choices = execute_query(__query_string, convert_to_dict=False)
    recipe_type = SelectField(label="Recipe Type", choices=__recipe_type_choices)
    # Hidden fields
    recipe_creationGMT = StringField(label="CreationGMT")
    recipe_id = IntegerField(label="Recipe ID")
    # submit
    submit = SubmitField(label="Save Changes")


class RecipeInstructionForm(FlaskForm):
    instruction = TextAreaField(label="Instruction")
    # Hidden fields
    instruction_id = StringField(label="Instruction ID")
    recipe_id = IntegerField(label="Recipe ID")
    # submit
    submit = SubmitField(label="Save Change")


class RecipeIngredientForm(FlaskForm):
    __query_string = "SELECT IngredientNameID, IngredientName FROM CBIngredientName ORDER BY 2 ASC"
    __ingredient_name_choices = execute_query(__query_string, convert_to_dict=False)
    ingredient_name = SelectField(label="Ingredient", choices=__ingredient_name_choices)
    ingredient_name_new = StringField(label="New Ingredient", render_kw={"placeholder": "New ingredient"})
    __query_string = "SELECT PrepID, LongName FROM CBIngredientPrep ORDER BY 2 ASC"
    __ingredient_prep_choices = execute_query(__query_string, convert_to_dict=False)
    ingredient_prep = SelectField(label="Prep", choices=__ingredient_prep_choices)
    ingredient_prep_new = StringField(label="New Prep", render_kw={"placeholder": "New preparation"})
    ingredient_quantity = DecimalField(label="Quantity")
    __query_string = "SELECT IngredientUnitID, LongName FROM CBIngredientUnit ORDER BY 2 ASC"
    __ingredient_unit_choices = execute_query(__query_string, convert_to_dict=False)
    ingredient_unit = SelectField(label="Unit", choices=__ingredient_unit_choices)
    ingredient_unit_new = StringField(label="New Unit", render_kw={"placeholder": "New unit"})
    is_vegetarian = BooleanField(label="Vegetarian")
    is_searchable = BooleanField(label="Searchable")
    __query_string = "SELECT DISTINCT SearchName, SearchName FROM CBIngredientName ORDER BY 2 ASC"
    __ingredient_search_name = execute_query(__query_string, convert_to_dict=False)
    search_name = SelectField(label="Search Term", choices=__ingredient_search_name)
    search_name_new = StringField(label="New Search Term", render_kw={"placeholder": "Pasta, Chicken, Etc."})
    __query_string = "SELECT -1, '' UNION SELECT RecipeID, RecipeName FROM CBRecipe ORDER BY 2 ASC"
    __recipes = execute_query(__query_string, convert_to_dict=False)
    linked_recipe = SelectField(label="Linked Recipe", choices=__recipes)
    # Hidden fields
    ingredient_id = StringField(label="Ingredient ID")
    recipe_id = IntegerField(label="Recipe ID")
    # submit
    submit = SubmitField(label="Submit")


class RecipeNutritionForm(FlaskForm):
    __query_string = "SELECT ElementNameID, LongName FROM CBElementName ORDER BY 2 ASC"
    __nutrition_element_names = execute_query(__query_string, convert_to_dict=False)
    nutrition_name = SelectField(label="Nutrition Element", choices=__nutrition_element_names)
    nutrition_value = DecimalField(label="Amount")
    # Hidden fields
    nutrition_id = StringField(label="Nutrition ID")
    recipe_id = IntegerField(label="Recipe ID")
    # submit
    submit = SubmitField(label="Save Changes")


class RecipeTagForm(FlaskForm):
    __query_string = "SELECT TagID, TagName FROM CBTagName ORDER BY 2 ASC"
    __tag_names = execute_query(__query_string, convert_to_dict=False)
    tag_name = SelectField(label="Recipe Tag", choices=__tag_names)
    tag_name_new = StringField(label="New Tag Name", render_kw={"placeholder": "New tag"})
    # Hidden fields
    recipe_id = IntegerField(label="Recipe ID")
    # submit
    submit = SubmitField(label="Save")


class RecipeSearchForm(FlaskForm):
    __query_string = "SELECT '0', 'All' " \
                     "UNION " \
                     "SELECT RecipeTypeID, LongName " \
                     "FROM CBRecipeType " \
                     "ORDER BY 2 ASC"
    __recipe_types = execute_query(__query_string, convert_to_dict=False)
    recipe_type = SelectField(label="Recipe Type: ", choices=__recipe_types)
    __query_string = "SELECT DISTINCT SearchName, SearchName " \
                     "FROM CBIngredientName " \
                     "WHERE SearchName != 'Not Searchable' " \
                     "ORDER BY 2 ASC"
    __recipe_ingredients = execute_query(__query_string, convert_to_dict=False)
    __recipe_ingredients.insert(0, ('All', "All"))  # wildcard option manually added for this field
    recipe_ingredient = SelectField(label="Ingredient: ", choices=__recipe_ingredients, default=0)
    search_term = StringField(label="Search Keyword: ", render_kw={"placeholder": "ex: Taco"})
    vegetarian = BooleanField(label="Vegetarian")
    low_fat = BooleanField(label="Low Fat")
    low_calorie = BooleanField(label="Low Calorie")
    quick_meal = BooleanField(label="Quick Meal")
    random = BooleanField(label="Pick one for me")
    # submit
    submit = SubmitField(label="Search")


class DatabaseForm(FlaskForm):
    SQL_string = TextAreaField(label="SQL")
    response = TextAreaField(label="Response")
    # submit
    submit = SubmitField(label="Execute")


class EmailRecipeForm(FlaskForm):
    recipe_name = StringField(label="Recipe Name:", render_kw={"placeholder": "Tacos de chorizo"})
    recipe_source = StringField(label="Recipe Source:", render_kw={"placeholder": "www.someplace.com / Memom's secret recipe."})
    total_time = IntegerField(label="Total Time:")
    servings = IntegerField(label="Servings:")
    instructions = TextAreaField(label="Instructions:", render_kw={"placeholder": "Step 1: Bend the taco shells.."})
    ingredients = TextAreaField(label="Ingredients:", render_kw={"placeholder": "Flat tortillas x6, chorizo x3lbs.."})
    nutrition = TextAreaField(label="Nutrition:", render_kw={"placeholder": "Sat fat: 2g, Calories: 600.."})
    # submit
    submit = SubmitField(label="Send to Dan!")


