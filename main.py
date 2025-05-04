import flet as ft
import asyncio
from datetime import datetime
import database as db
import csv
import json
import io
import os
import translations as tr  # Import the translations module
import time

# Sample data for initial setup - will be migrated to the database on first run
SAMPLE_WORDS = [
    {"word": "apple", "definition": "A fruit that is red or green.", "date_added": "2024-03-15"},
    {"word": "banana", "definition": "A long yellow fruit.", "date_added": "2024-03-15"},
    {"word": "cat", "definition": "A small domesticated carnivorous mammal.", "date_added": "2024-03-15"},
    {"word": "dog", "definition": "A domesticated carnivorous mammal.", "date_added": "2024-03-15"},
]

# Migrate sample data to the database if needed
def migrate_sample_data():
    # Check if database is empty
    words = db.get_all_words()
    if not words:
        print("Initializing database with sample data...")
        for word_data in SAMPLE_WORDS:
            db.add_word(word_data["word"], word_data["definition"])
        print("Sample data migration complete.")


class SplashScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.init_content()

    def init_content(self):
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK

        # Color scheme based on theme
        if is_dark:
            bg_gradient = [ft.Colors.BLUE_900, ft.Colors.BLACK]
            accent_color = ft.Colors.BLUE_200  # Lighter blue for dark mode
            text_color = ft.Colors.GREY_100  # Light grey for better readability
            secondary_color = ft.Colors.with_opacity(0.8, ft.Colors.GREY_300)
        else:
            bg_gradient = [ft.Colors.BLUE_50, ft.Colors.WHITE]
            accent_color = ft.Colors.BLUE_800  # Darker blue for light mode
            text_color = ft.Colors.GREY_900  # Dark grey for better readability
            secondary_color = ft.Colors.with_opacity(0.8, ft.Colors.GREY_800)

        # Background gradient based on theme
        gradient = ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=bg_gradient
        )

        # Main content container
        self.content = ft.Container(
            content=ft.Column(
                [
                    # Logo/Icon
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.BOOK,
                            size=100,
                            color=accent_color
                        ),
                        margin=ft.margin.only(top=80),
                        animate=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        animate_opacity=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        opacity=0
                    ),

                    # App Name
                    ft.Container(
                        content=ft.Text(
                            tr.get_text("app_name"),
                            size=36,
                            weight=ft.FontWeight.W_900,
                            color=text_color
                        ),
                        margin=ft.margin.only(top=20),
                        animate=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        animate_opacity=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        opacity=0
                    ),

                    # Tagline
                    ft.Container(
                        content=ft.Text(
                            tr.get_text("tagline"),
                            size=16,
                            italic=True,
                            color=secondary_color
                        ),
                        margin=ft.margin.only(top=10),
                        animate=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        animate_opacity=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
                        opacity=0
                    ),

                    # Loading animation
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(
                                    width=10,
                                    height=10,
                                    border_radius=5,
                                    bgcolor=accent_color,
                                    animate=ft.animation.Animation(1000, ft.AnimationCurve.EASE_IN_OUT),
                                    animate_opacity=ft.animation.Animation(1000, ft.AnimationCurve.EASE_IN_OUT),
                                    opacity=0
                                ) for _ in range(3)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10
                        ),
                        margin=ft.margin.only(top=40)
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0
            ),
            gradient=gradient,
            expand=True
        )

    async def show(self):
        # Add to page
        self.page.add(self.content)
        self.page.update()

        # Fade in elements sequentially
        for control in self.content.content.controls[:-1]:  # Exclude loading dots
            control.opacity = 1
            self.page.update()
            await asyncio.sleep(0.2)

        # Animate loading dots
        dots = self.content.content.controls[-1].content.controls
        while True:
            for i, dot in enumerate(dots):
                await asyncio.sleep(0.2)
                dot.animate = ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
                dot.scale = 1.5
                dot.opacity = 1
                self.page.update()
                await asyncio.sleep(0.2)
                dot.scale = 1
                dot.opacity = 0.5
                self.page.update()

    async def hide(self):
        # Fade out elements
        for control in reversed(self.content.content.controls):
            control.opacity = 0
            self.page.update()
            await asyncio.sleep(0.1)

        await asyncio.sleep(0.5)
        self.page.clean()


class DictionaryApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = tr.get_text("app_name")
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.padding = 0
        self.page.spacing = 0
        self.page.window_width = 800
        self.page.window_height = 600
        self.page.window_min_width = 400
        self.page.window_min_height = 500

        # Initialize current_word to avoid reference errors
        self.current_word = None
        
        # For search throttling
        self.last_search_time = datetime.now()
        self.search_throttle = 0.3  # seconds
        
        # Current language
        self.current_language = tr.DEFAULT_LANGUAGE

        # Theme colors
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK

        # Color scheme based on theme
        if is_dark:
            self.primary_color = ft.Colors.BLUE_300  # Softer blue for dark mode
            self.surface_color = ft.Colors.with_opacity(0.05, ft.Colors.WHITE)  # Very subtle surface color
            self.on_surface_color = ft.Colors.with_opacity(0.7, ft.Colors.WHITE)  # Softer text on surface
            self.error_color = ft.Colors.RED_300  # Softer red for dark mode
            self.background_color = ft.Colors.with_opacity(0.02, ft.Colors.WHITE)  # Very subtle background
            self.text_color = ft.Colors.with_opacity(0.9, ft.Colors.WHITE)  # Slightly softer white for text
        else:
            self.primary_color = ft.Colors.BLUE_800
            self.surface_color = ft.Colors.SURFACE
            self.on_surface_color = ft.Colors.ON_SURFACE
            self.error_color = ft.Colors.RED_600
            self.background_color = ft.Colors.WHITE
            self.text_color = ft.Colors.GREY_900

        # Initialize components
        self.init_app_bar()
        self.init_search_section()
        self.init_add_section()
        self.init_settings_section()
        self.init_navigation()

        # Set initial state
        self.update_theme()
        
        # Ensure all UI elements have the correct language
        self.refresh_ui_language()

    def init_app_bar(self):
        self.app_bar = ft.AppBar(
            leading=ft.Icon(ft.Icons.BOOK, color=self.primary_color),
            title=ft.Text(tr.get_text("app_name", self.current_language), weight=ft.FontWeight.BOLD),
            center_title=True,
            bgcolor=self.surface_color,
            actions=[
                ft.IconButton(
                    icon=ft.Icons.BRIGHTNESS_4,
                    on_click=self.toggle_theme,
                    tooltip=tr.get_text("dark_mode", self.current_language)
                ),
                ft.IconButton(
                    icon=ft.Icons.INFO_OUTLINED,
                    on_click=self.show_about_dialog,
                    tooltip=tr.get_text("about", self.current_language)
                )
            ]
        )
        self.page.appbar = self.app_bar

    def init_search_section(self):
        # Search field with icon
        self.search_field = ft.TextField(
            label=tr.get_text("search_placeholder", self.current_language),
            prefix_icon=ft.Icons.SEARCH,
            border_radius=10,
            on_change=self.on_search_field_change,  # Change to a debounced handler
            on_submit=self.update_search_results,   # Add on_submit for immediate search on Enter
            autofocus=True,
            expand=True,
        )

        # Search results container (left panel)
        self.search_results = ft.ListView(
            expand=1,
            spacing=10,
            padding=10,
            auto_scroll=False  # Disable auto-scrolling
        )

        # Definition panel (right side)
        self.definition_panel = ft.Container(
            visible=False,
            bgcolor=self.surface_color,
            border_radius=10,
            padding=20,
            expand=1,
            content=ft.Column([
                ft.Row([
                    ft.Text(
                        "",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        expand=True
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        tooltip=tr.get_text("edit", self.current_language),
                        icon_color=ft.Colors.BLUE,
                        on_click=self.edit_word
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        tooltip=tr.get_text("delete", self.current_language),
                        icon_color=ft.Colors.RED_400,
                        on_click=self.delete_word
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        tooltip=tr.get_text("close", self.current_language),
                        icon_color=ft.Colors.GREY_600,
                        on_click=self.close_definition_panel
                    )
                ]),
                ft.Divider(),
                ft.Text(
                    "",
                    size=16,
                    selectable=True
                ),
                ft.Text(
                    "",
                    size=12,
                    color=ft.Colors.with_opacity(0.5, self.on_surface_color)
                )
            ])
        )

        # We'll create dialogs dynamically when needed instead of storing them as instance variables

        self.search_section = ft.Container(
            content=ft.Row([
                # Left panel with search and results
                ft.Column([
                    ft.Container(
                        content=self.search_field,
                        padding=20,
                        bgcolor=self.surface_color,
                        border_radius=10,
                        shadow=ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=15,
                            color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                            offset=ft.Offset(0, 0)
                        )
                    ),
                    self.search_results
                ], expand=1),
                # Right panel for definition
                self.definition_panel
            ]),
            expand=True
        )

        # Show all words by default when the search tab is initialized
        self.update_search_results()

    def init_add_section(self):
        self.add_word_field = ft.TextField(
            label=tr.get_text("word_label", self.current_language),
            prefix_icon=ft.Icons.TEXT_FIELDS,
            border_radius=10,
            expand=True
        )

        self.add_def_field = ft.TextField(
            label=tr.get_text("definition_label", self.current_language),
            prefix_icon=ft.Icons.DESCRIPTION,
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_radius=10,
            expand=True
        )

        self.add_button = ft.ElevatedButton(
            text=tr.get_text("add_word_button", self.current_language),
            icon=ft.Icons.ADD,
            on_click=self.add_word,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=20
            )
        )

        self.add_section = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Column([
                        self.add_word_field,
                        self.add_def_field,
                        self.add_button
                    ], spacing=20),
                    padding=20,
                    bgcolor=self.surface_color,
                    border_radius=10,
                    shadow=ft.BoxShadow(
                        spread_radius=1,
                        blur_radius=15,
                        color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                        offset=ft.Offset(0, 0)
                    )
                )
            ]),
            padding=20,
            expand=True
        )

    def init_settings_section(self):
        self.dark_mode_switch = ft.Switch(
            label=tr.get_text("dark_mode", self.current_language),
            value=self.page.theme_mode == ft.ThemeMode.DARK,
            on_change=self.toggle_theme
        )

        # Get language options from translations
        language_options = tr.get_language_options()
        
        # Create dropdown options with the code as the value and name as display text
        dropdown_options = []
        for lang in language_options:
            # Create option with code as key and name as text
            dropdown_options.append(ft.dropdown.Option(
                text=lang["name"],  # What user sees
                key=lang["code"]    # What's used internally as value
            ))
        
        # Initialize dropdown with correct language code
        self.language_dropdown = ft.Dropdown(
            label=tr.get_text("language", self.current_language),
            options=dropdown_options,
            value=self.current_language,  # Set to current language code
            border_radius=10,
            on_change=self.handle_language_change
        )
        
        # Import section
        # Create dropdown with tooltip
        import_dropdown = ft.Dropdown(
            label=tr.get_text("import_format", self.current_language),
            options=[
                ft.dropdown.Option("CSV"),
                ft.dropdown.Option("JSON")
            ],
            value="CSV",
            border_radius=10,
            width=200
        )
        
        # In Flet 0.27+, tooltip needs to be created differently
        self.import_format_dropdown = ft.Container(
            content=import_dropdown,
            tooltip=tr.get_text("import_description", self.current_language)
        )
        
        self.file_picker = ft.FilePicker(
            on_result=self.on_file_picked
        )
        self.page.overlay.append(self.file_picker)
        
        self.import_feedback = ft.Text(
            size=14,
            color=self.on_surface_color
        )
        
        self.import_status = ft.Text(
            size=14,
            visible=False
        )
        
        self.import_button = ft.ElevatedButton(
            tr.get_text("import_button", self.current_language),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.file_picker.pick_files(
                allowed_extensions=["csv", "json"],
                dialog_title=tr.get_text("select_file", self.current_language)
            )
        )
        
        # Create sample file download section
        self.download_csv_button = ft.TextButton(
            tr.get_text("download_csv_template", self.current_language),
            icon=ft.Icons.DOWNLOAD,
            on_click=self.download_csv_template
        )
        
        self.download_json_button = ft.TextButton(
            tr.get_text("download_json_template", self.current_language),
            icon=ft.Icons.DOWNLOAD,
            on_click=self.download_json_template
        )
        
        # Create import section container with styling
        self.import_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.UPLOAD_FILE, color=self.primary_color),
                    ft.Text(tr.get_text("import_words", self.current_language), size=18, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Text(
                    tr.get_text("import_description", self.current_language),
                    size=14,
                    color=ft.Colors.with_opacity(0.7, self.on_surface_color)
                ),
                # Add dropdown with tooltip
                self.import_format_dropdown,
                ft.Row([
                    self.import_button,
                    ft.Container(width=10),  # Spacer
                    self.import_feedback,
                ], alignment=ft.MainAxisAlignment.START),
                self.import_status,
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.2, self.on_surface_color)),
                ft.Row([
                    ft.Icon(ft.Icons.DOWNLOAD, color=self.primary_color, size=16),
                    ft.Text(tr.get_text("download_templates", self.current_language), size=14),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Row([
                    self.download_csv_button,
                    self.download_json_button,
                ], alignment=ft.MainAxisAlignment.START),
            ], spacing=10),
            padding=20,
            bgcolor=ft.Colors.with_opacity(0.05, self.on_surface_color),
            border_radius=10,
            width=500,
            margin=ft.margin.only(top=10)
        )

        # Create a scrollable container for settings
        self.settings_section = ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Container(
                                content=ft.Column(
                                    [
                                        self.dark_mode_switch,
                                        self.language_dropdown,
                                        ft.Divider(),
                                        ft.ListTile(
                                            leading=ft.Icon(ft.Icons.INFO),
                                            title=ft.Text(tr.get_text("app_name", self.current_language)),
                                            subtitle=ft.Text(tr.get_text("version", self.current_language)),
                                            trailing=ft.Text(tr.get_text("copyright", self.current_language))
                                        )
                                    ],
                                    spacing=20
                                ),
                                padding=20,
                                bgcolor=self.surface_color,
                                border_radius=10,
                                shadow=ft.BoxShadow(
                                    spread_radius=1,
                                    blur_radius=15,
                                    color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                                    offset=ft.Offset(0, 0)
                                )
                            ),
                            # Add import section
                            self.import_section
                        ],
                        spacing=20,
                        scroll=ft.ScrollMode.AUTO,  # Add scrolling to the inner column
                        expand=True
                    )
                ]
            ),
            padding=20,
            expand=True
        )

    def init_navigation(self):
        self.sections = [self.search_section, self.add_section, self.settings_section]

        self.nav_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(
                    icon=ft.Icons.SEARCH,
                    selected_icon=ft.Icons.SEARCH,
                    label=tr.get_text("search_tab", self.current_language)
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.ADD,
                    selected_icon=ft.Icons.ADD,
                    label=tr.get_text("add_tab", self.current_language)
                ),
                ft.NavigationBarDestination(
                    icon=ft.Icons.SETTINGS,
                    selected_icon=ft.Icons.SETTINGS,
                    label=tr.get_text("settings_tab", self.current_language)
                )
            ],
            selected_index=0,
            on_change=self.on_nav_change,
            bgcolor=self.surface_color,
            elevation=10
        )

        self.page.navigation_bar = self.nav_bar
        self.page.add(*self.sections)

        # Set initial visibility
        for i, section in enumerate(self.sections):
            section.visible = (i == 0)

    def update_theme(self):
        is_dark = self.page.theme_mode == ft.ThemeMode.DARK
        if is_dark:
            self.primary_color = ft.Colors.BLUE_300  # Softer blue for dark mode
            self.surface_color = ft.Colors.with_opacity(0.05, ft.Colors.WHITE)  # Very subtle surface color
            self.on_surface_color = ft.Colors.with_opacity(0.7, ft.Colors.WHITE)  # Softer text on surface
            self.error_color = ft.Colors.RED_300  # Softer red for dark mode
            self.background_color = ft.Colors.with_opacity(0.02, ft.Colors.WHITE)  # Very subtle background
            self.text_color = ft.Colors.with_opacity(0.9, ft.Colors.WHITE)  # Slightly softer white for text
        else:
            self.primary_color = ft.Colors.BLUE_800
            self.surface_color = ft.Colors.SURFACE
            self.on_surface_color = ft.Colors.ON_SURFACE
            self.error_color = ft.Colors.RED_600
            self.background_color = ft.Colors.WHITE
            self.text_color = ft.Colors.GREY_900
        self.page.update()

    def toggle_theme(self, e):
        self.page.theme_mode = (
            ft.ThemeMode.LIGHT if self.page.theme_mode == ft.ThemeMode.DARK
            else ft.ThemeMode.DARK
        )
        self.update_theme()

    def show_about_dialog(self, e):
        self.page.dialog = ft.AlertDialog(
            title=ft.Text(tr.get_text("about", self.current_language) + " " + tr.get_text("app_name", self.current_language)),
            content=ft.Column([
                ft.Text(tr.get_text("about_content", self.current_language)),
                ft.Text(tr.get_text("version", self.current_language)),
                ft.Text(tr.get_text("copyright", self.current_language))
            ], tight=True),
            actions=[
                ft.TextButton(tr.get_text("close", self.current_language), on_click=lambda e: self.close_dialog())
            ]
        )
        if self.page.dialog not in self.page.controls:
            self.page.controls.append(self.page.dialog)
        self.page.dialog.open = True
        self.page.update()

    def close_dialog(self, e=None):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def edit_word(self, e):
        print(f"Edit clicked. Current word: {self.current_word['word'] if self.current_word else 'None'}")  # Debug log
        if not self.current_word:
            self.show_snackbar(tr.get_text("no_word_selected", self.current_language), self.error_color)
            return

        # Create new dialog components first
        edit_word_field = ft.TextField(
            label=tr.get_text("word_label", self.current_language),
            value=self.current_word["word"],
            border_radius=10,
            expand=True
        )

        edit_def_field = ft.TextField(
            label=tr.get_text("definition_label", self.current_language),
            value=self.current_word["definition"],
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_radius=10,
            expand=True
        )

        def save_edit_handler(e):
            word = edit_word_field.value.strip()
            definition = edit_def_field.value.strip()

            if not word or not definition:
                # Keep dialog open, show error within dialog or via snackbar
                self.show_snackbar(tr.get_text("fields_required", self.current_language), self.error_color)
                # Optionally add error text to dialog content here
                return

            # Update word in database
            word_id = self.current_word["id"]
            updated = db.update_word(word_id, word, definition)

            if updated:
                # Update the current_word state
                self.current_word["word"] = word
                self.current_word["definition"] = definition
                self.show_definition(self.current_word) # Refresh definition panel

                # Close dialog FIRST
                self.close_dialog()
                # THEN update search results
                self.update_search_results()
                self.show_snackbar(f"'{word}' " + tr.get_text("updated_successfully", self.current_language), self.primary_color)
            else:
                self.show_snackbar(f"'{word}' " + tr.get_text("error_updating", self.current_language), self.error_color)
                self.close_dialog()

        # Define the dialog structure
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(tr.get_text("edit_word", self.current_language)),
            content=ft.Container(
                content=ft.Column([
                    edit_word_field,
                    edit_def_field
                ], tight=True, spacing=20),
                padding=20,
                width=400 # Give the dialog a specific width
            ),
            actions=[
                ft.TextButton(tr.get_text("cancel", self.current_language), on_click=self.close_dialog),
                ft.TextButton(tr.get_text("save", self.current_language), on_click=save_edit_handler)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        if dialog not in self.page.controls:
            self.page.controls.append(dialog)
        self.page.dialog = dialog
        self.page.dialog.open = True
        self.page.update() # Force UI update

        print("Opening dialog:", self.page.dialog)

    def delete_word(self, e):
        print(f"Delete clicked. Current word: {self.current_word['word'] if self.current_word else 'None'}") # Debug log
        if not self.current_word:
            self.show_snackbar(tr.get_text("no_word_selected", self.current_language), self.error_color)
            return
        
        word_to_delete = self.current_word["word"] # Capture word before dialog
        word_id = self.current_word["id"]  # Capture ID for database deletion
            
        def confirm_delete_handler(e):
            # Delete word from database
            deleted = db.delete_word(word_id)
            
            if deleted:
                # Clear selection and hide panel
                self.definition_panel.visible = False
                self.current_word = None
                
                # Close dialog FIRST
                self.close_dialog()
                # THEN update search results
                self.update_search_results()
                self.show_snackbar(f"'{word_to_delete}' " + tr.get_text("deleted_successfully", self.current_language), self.primary_color)
            else:
                self.show_snackbar(f"'{word_to_delete}' " + tr.get_text("error_deleting", self.current_language), self.error_color)
                self.close_dialog() # Close dialog even if delete failed

        # Define the dialog structure
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{tr.get_text('delete_word_confirm', self.current_language)} '{word_to_delete}'?"),
            content=ft.Text(tr.get_text("delete_warning", self.current_language)),
            actions=[
                ft.TextButton(tr.get_text("cancel", self.current_language), on_click=self.close_dialog),
                # Add color to delete button for emphasis
                ft.TextButton(tr.get_text("delete", self.current_language), on_click=confirm_delete_handler, style=ft.ButtonStyle(color=self.error_color)) 
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        if dialog not in self.page.controls:
            self.page.controls.append(dialog)
        self.page.dialog = dialog
        self.page.dialog.open = True
        self.page.update() # Force UI update

        print("Opening dialog:", self.page.dialog)

    def show_definition(self, word_data):
        self.current_word = word_data
        title = self.definition_panel.content.controls[0].controls[0]
        definition = self.definition_panel.content.controls[2]
        date = self.definition_panel.content.controls[3]

        title.value = word_data["word"]
        definition.value = word_data["definition"]
        date.value = f"{tr.get_text('added_on', self.current_language)} {word_data['date_added']}"

        self.definition_panel.visible = True
        self.page.update()

    def update_search_results(self, e=None):
        self.definition_panel.visible = False
        self.current_word = None
        query = ""
        if e is not None and hasattr(e, "control") and hasattr(e.control, "value"):
            query = e.control.value.lower()
        
        # Save current scroll position if possible
        current_scroll = getattr(self.search_results, "scroll_to", None)
        
        # Clear and update the list
        self.search_results.controls.clear()

        # Get words from database based on search query
        words = db.search_words(query) if query else db.get_all_words()

        # Populate the search results
        for entry in words:
            self.search_results.controls.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text(
                                entry["word"],
                                size=18,
                                weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                entry["definition"][:100] + ("..." if len(entry["definition"]) > 100 else ""),
                                size=14,
                                color=ft.Colors.with_opacity(0.7, self.on_surface_color)
                            )
                        ], spacing=5),
                        padding=15,
                        on_click=lambda e, word=entry: self.handle_word_click(word)
                    ),
                    elevation=2,
                    margin=5
                )
            )
            
        # Update the UI without forcing scroll to bottom
        self.page.update()

    def handle_word_click(self, word_data):
        print(f"Word clicked: {word_data['word']}")  # Debug log
        self.show_definition(word_data)
        print(f"Current word set to: {self.current_word['word'] if self.current_word else 'None'}")  # Debug log

    def add_word(self, e):
        word = self.add_word_field.value.strip()
        definition = self.add_def_field.value.strip()

        if not word or not definition:
            self.show_snackbar(tr.get_text("fields_required", self.current_language), self.error_color)
            return

        # Add word to database
        success = db.add_word(word, definition)
        
        if success:
            self.add_word_field.value = ""
            self.add_def_field.value = ""
            self.show_snackbar(f"'{word}' " + tr.get_text("added_successfully", self.current_language), self.primary_color)
            self.page.update()
        else:
            self.show_snackbar(f"'{word}' " + tr.get_text("error_adding", self.current_language), self.error_color)

    def show_snackbar(self, message, color):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=10)
        )
        self.page.snack_bar.open = True
        self.page.update()

    def on_nav_change(self, e):
        idx = e.control.selected_index
        for i, section in enumerate(self.sections):
            section.visible = (i == idx)
        self.page.update()

    def close_definition_panel(self, e=None):
        self.definition_panel.visible = False
        self.current_word = None
        self.page.update()

    def on_file_picked(self, e):
        """Handle the file picker result."""
        if not e.files or len(e.files) == 0:
            return
        
        file_info = e.files[0]
        file_path = file_info.path
        file_name = file_info.name
        file_size = os.path.getsize(file_path)
        
        # Reset status displays
        self.import_feedback.value = f"Selected: {file_name} ({self._format_file_size(file_size)})"
        self.import_feedback.color = self.on_surface_color
        self.import_status.visible = False
        self.page.update()
        
        # Check file extension against chosen format
        file_ext = os.path.splitext(file_name)[1].lower()
        # Get value from the dropdown inside the container
        dropdown_value = self.import_format_dropdown.content.value
        expected_ext = ".csv" if dropdown_value == "CSV" else ".json"
        
        if file_ext != expected_ext:
            self.import_feedback.value = f"Error: File extension '{file_ext}' doesn't match selected format '{expected_ext}'"
            self.import_feedback.color = self.error_color
            self.page.update()
            return
        
        # For larger files, skip preview and offer direct import
        large_file_threshold = 10 * 1024 * 1024  # 10 MB
        
        if file_size > large_file_threshold:
            self._show_large_file_dialog(file_path, file_ext, file_size)
            return
            
        # Show processing indicator for smaller files
        self.import_feedback.value = "Loading preview..."
        self.page.update()
        
        # Get file preview and show confirmation dialog
        try:
            preview_entries = self._get_file_preview(file_path, file_ext)
            if preview_entries:
                self._show_import_preview_dialog(file_path, file_ext, preview_entries)
            else:
                self.import_feedback.value = "Error: Could not read file or file is empty"
                self.import_feedback.color = self.error_color
                self.page.update()
        except Exception as ex:
            self.import_feedback.value = f"Error: {str(ex)}"
            self.import_feedback.color = self.error_color
            self.page.update()
    
    def _format_file_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"
    
    def _show_large_file_dialog(self, file_path, file_ext, file_size):
        """Show a dialog for handling large files."""
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Large File Detected"),
            content=ft.Column([
                ft.Text(
                    f"File size: {self._format_file_size(file_size)}",
                    size=16,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    "This is a large file. Preview is disabled to improve performance.",
                    size=14
                ),
                ft.Text(
                    "Would you like to proceed with importing this file?",
                    size=14
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            "Choose processing options:",
                            size=14,
                            weight=ft.FontWeight.BOLD
                        ),
                        # Options for large file processing
                        ft.Checkbox(
                            label="Skip duplicate words (faster)",
                            value=True,
                        ),
                        ft.Checkbox(
                            label="Show progress updates",
                            value=True,
                        )
                    ]),
                    padding=10,
                    margin=ft.margin.only(top=10)
                )
            ]),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.TextButton(
                    "Start Import",
                    on_click=lambda e: self._process_import_file(file_path, file_ext, large_file=True)
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        if dialog not in self.page.controls:
            self.page.controls.append(dialog)
        self.page.dialog = dialog
        self.page.dialog.open = True
        self.page.update()

    def _get_file_preview(self, file_path, file_ext, max_entries=5):
        """Get a preview of the first few entries from the file."""
        preview_entries = []
        
        try:
            if file_ext == ".csv":
                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    # Only read a small portion of the file for header detection
                    sample = csvfile.read(4096)  # Read first 4KB to detect headers
                    if not sample.strip():
                        return []
                    
                    # Reset file pointer
                    csvfile.seek(0)
                    
                    # Parse CSV headers
                    reader = csv.reader([sample.split('\n')[0]])
                    headers = next(reader, None)
                    
                    # Validate headers
                    if not headers or 'word' not in [h.lower() for h in headers] or 'definition' not in [h.lower() for h in headers]:
                        return []
                    
                    # Find column indexes
                    word_idx = [h.lower() for h in headers].index('word')
                    def_idx = [h.lower() for h in headers].index('definition')
                    
                    # Reset the file pointer again to read the actual content
                    csvfile.seek(0)
                    # Skip the header row
                    next(csv.reader(csvfile))
                    
                    # Get only first few entries for preview
                    count = 0
                    content_reader = csv.reader(csvfile)
                    for row in content_reader:
                        if count >= max_entries:
                            break
                            
                        if len(row) <= max(word_idx, def_idx):
                            continue
                            
                        word = row[word_idx].strip()
                        definition = row[def_idx].strip()
                        
                        if not word or not definition:
                            continue
                        
                        preview_entries.append({"word": word, "definition": definition})
                        count += 1
                        
            else:  # JSON
                # Use streaming JSON parsing for first few entries
                # IMPORTANT: Open in binary mode for ijson
                with open(file_path, 'rb') as jsonfile:
                    # Read just enough to parse header structure
                    start_bytes = jsonfile.read(1024)  # Read first 1KB
                    
                    # Check if it starts as a JSON array
                    if not start_bytes.lstrip().startswith(b'['):
                        return []
                    
                    # Reset file pointer
                    jsonfile.seek(0)
                    
                    # Use ijson for incremental JSON parsing if available
                    try:
                        import ijson
                        items = ijson.items(jsonfile, 'item')
                        
                        # Get first few entries
                        count = 0
                        for entry in items:
                            if count >= max_entries:
                                break
                                
                            if not isinstance(entry, dict):
                                continue
                                
                            word = entry.get('word', '').strip()
                            definition = entry.get('definition', '').strip()
                            
                            if not word or not definition:
                                continue
                            
                            preview_entries.append({"word": word, "definition": definition})
                            count += 1
                    
                    except ImportError:
                        # Fallback to standard json if ijson not available
                        # But need to reopen the file in text mode for json.load
                        jsonfile.close()
                        with open(file_path, 'r', encoding='utf-8') as textfile:
                            # But only read a small part for preview
                            data = json.load(textfile)
                            
                            # Check if data is a list
                            if not isinstance(data, list):
                                return []
                            
                            # Get preview entries
                            count = 0
                            for entry in data[:max_entries]:
                                if not isinstance(entry, dict):
                                    continue
                                    
                                word = entry.get('word', '').strip()
                                definition = entry.get('definition', '').strip()
                                
                                if not word or not definition:
                                    continue
                                
                                preview_entries.append({"word": word, "definition": definition})
                                count += 1
                        
        except Exception as ex:
            print(f"Preview error: {ex}")
            return []
            
        return preview_entries

    def _show_import_preview_dialog(self, file_path, file_ext, preview_entries):
        """Show a dialog with a preview of entries and confirm import."""
        # Create preview list
        preview_list = ft.ListView(
            height=200,
            spacing=10,
            padding=10,
            auto_scroll=True
        )
        
        # Add preview entries
        for entry in preview_entries:
            preview_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            entry["word"],
                            size=16,
                            weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            entry["definition"],
                            size=14,
                            color=ft.Colors.with_opacity(0.7, self.on_surface_color)
                        )
                    ]),
                    padding=10,
                    bgcolor=ft.Colors.with_opacity(0.05, self.on_surface_color),
                    border_radius=10
                )
            )
        
        # Create dialog
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import Preview"),
            content=ft.Column([
                ft.Text(
                    f"Preview of first {len(preview_entries)} entries from file. Continue with import?",
                    size=14
                ),
                ft.Container(
                    content=preview_list,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.2, self.on_surface_color)),
                    border_radius=10,
                    padding=10,
                    margin=10
                ),
                ft.Text(
                    "Note: Duplicate words will be skipped.",
                    size=12,
                    italic=True,
                    color=ft.Colors.with_opacity(0.6, self.on_surface_color)
                )
            ]),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.TextButton(
                    "Import",
                    on_click=lambda e: self._process_import_file(file_path, file_ext)
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        # Show dialog
        if dialog not in self.page.controls:
            self.page.controls.append(dialog)
        self.page.dialog = dialog
        self.page.dialog.open = True
        self.page.update()
    
    def _process_import_file(self, file_path, file_ext, large_file=False):
        """Process the import after confirmation."""
        # Close dialog
        self.close_dialog()
        
        # Create progress bar
        self.import_progress = ft.ProgressBar(width=400, color=self.primary_color)
        
        # Add progress bar to import section (insert before the import status)
        progress_index = self.import_section.content.controls.index(self.import_status)
        self.import_section.content.controls.insert(progress_index, self.import_progress)
        
        # Show processing indicator
        self.import_feedback.value = "Processing file..."
        self.page.update()
        
        # Import the file
        try:
            if file_ext == ".csv":
                import_results = self.import_csv_file(file_path, large_file=large_file)
            else:  # .json
                import_results = self.import_json_file(file_path, large_file=large_file)
            
            # Display results
            success_count = import_results["success"]
            error_count = import_results["error"]
            
            if success_count > 0 or error_count > 0:
                self.import_status.value = f"✅ {success_count} words imported | ❌ {error_count} errors"
                self.import_status.visible = True
                
                if success_count > 0:
                    self.import_feedback.value = "Import completed successfully."
                    self.import_feedback.color = self.primary_color
                    # Refresh the word list in search tab
                    self.update_search_results()
                else:
                    self.import_feedback.value = "Import completed with errors."
                    self.import_feedback.color = self.error_color
            else:
                self.import_feedback.value = "No valid entries found in file."
                self.import_feedback.color = self.error_color
                
            # Remove progress bar
            self.import_section.content.controls.remove(self.import_progress)
            self.page.update()
            
        except Exception as ex:
            self.import_feedback.value = f"Error: {str(ex)}"
            self.import_feedback.color = self.error_color
            
            # Remove progress bar
            self.import_section.content.controls.remove(self.import_progress)
            self.page.update()

    def import_csv_file(self, file_path, large_file=False):
        """Import words from a CSV file."""
        success_count = 0
        error_count = 0
        
        try:
            # Get file size for progress tracking
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Check file header format
                try:
                    # Only read first line to check headers
                    headers_line = csvfile.readline().strip()
                    if not headers_line:
                        return {"success": 0, "error": 0, "message": "File is empty"}
                    
                    # Parse headers
                    reader = csv.reader([headers_line])
                    headers = next(reader, None)
                    
                    # Validate headers
                    if not headers or 'word' not in [h.lower() for h in headers] or 'definition' not in [h.lower() for h in headers]:
                        return {"success": 0, "error": 1, "message": "Invalid CSV format. Headers must include 'word' and 'definition'"}
                    
                    # Find column indexes
                    word_idx = [h.lower() for h in headers].index('word')
                    def_idx = [h.lower() for h in headers].index('definition')
                    
                except Exception as e:
                    return {"success": 0, "error": 1, "message": f"Failed to parse CSV headers: {str(e)}"}
                
                # Reset file position and skip header
                csvfile.seek(0)
                next(csv.reader(csvfile))  # Skip header row
                
                # Process rows in chunks using streaming approach
                batch_size = 1000 if large_file else 100
                batch = []
                processed_bytes = len(headers_line) + 1  # Header line + newline
                last_update = 0
                
                # Create a custom CSV reader for streaming large files
                reader = csv.reader(csvfile)
                
                for row in reader:
                    # Update bytes processed for progress bar
                    line_bytes = sum(len(cell) for cell in row) + len(row) - 1
                    processed_bytes += line_bytes + 1  # +1 for newline
                    
                    # Update progress bar every 0.5% or every 500KB for large files
                    progress_pct = processed_bytes / file_size
                    update_threshold = 0.005 if large_file else 0.05
                    
                    if progress_pct - last_update > update_threshold or (large_file and processed_bytes - last_update * file_size > 500000):
                        self.import_progress.value = progress_pct
                        # Only update UI occasionally for large files to avoid slowdown
                        if large_file:
                            if int(progress_pct * 20) > int(last_update * 20):  # Update UI every 5%
                                self.import_feedback.value = f"Processing... {progress_pct:.1%} complete"
                                self.page.update()
                        else:
                            self.import_feedback.value = f"Processing... {progress_pct:.1%} complete"
                            self.page.update()
                        last_update = progress_pct
                    
                    # Process row data
                    if len(row) <= max(word_idx, def_idx):
                        error_count += 1
                        continue
                        
                    word = row[word_idx].strip()
                    definition = row[def_idx].strip()
                    
                    if not word or not definition:
                        error_count += 1
                        continue
                    
                    batch.append((word, definition))
                    
                    # Process batch when it reaches specified size
                    if len(batch) >= batch_size:
                        success, errors = self._process_import_batch(batch)
                        success_count += success
                        error_count += errors
                        batch = []
                
                # Process remaining entries
                if batch:
                    success, errors = self._process_import_batch(batch)
                    success_count += success
                    error_count += errors
                
        except Exception as e:
            raise Exception(f"Failed to process CSV file: {str(e)}")
        
        return {
            "success": success_count,
            "error": error_count,
            "message": f"Imported {success_count} words with {error_count} errors"
        }

    def import_json_file(self, file_path, large_file=False):
        """Import words from a JSON file."""
        success_count = 0
        error_count = 0
        
        try:
            # Get file size for progress tracking
            file_size = os.path.getsize(file_path)
            
            # Try to use ijson for streaming if available (better for large files)
            try:
                import ijson
                # Open file in binary mode as required by ijson
                with open(file_path, 'rb') as jsonfile:
                    # Validate it's a JSON array at the start
                    is_valid_array = False
                    for prefix, event, value in ijson.parse(jsonfile):
                        if prefix == '' and event == 'start_array':
                            is_valid_array = True
                            break
                    
                    if not is_valid_array:
                        return {"success": 0, "error": 1, "message": "JSON must contain an array of word entries"}
                
                    # Reset file position
                    jsonfile.seek(0)
                    
                    # Process entries in chunks via streaming
                    batch_size = 1000 if large_file else 100
                    batch = []
                    processed_items = 0
                    last_update_time = datetime.now()
                    
                    # Get items stream
                    items = ijson.items(jsonfile, 'item')
                    
                    for entry in items:
                        processed_items += 1
                        
                        # Update progress occasionally (can't track exact bytes)
                        current_time = datetime.now()
                        time_diff = (current_time - last_update_time).total_seconds()
                        
                        # Update UI about every second for large files
                        if time_diff > (1.0 if large_file else 0.5):
                            self.import_feedback.value = f"Processing... {processed_items} entries"
                            self.import_progress.value = None  # Show indeterminate progress
                            self.page.update()
                            last_update_time = current_time
                        
                        # Process entry
                        if not isinstance(entry, dict):
                            error_count += 1
                            continue
                            
                        word = entry.get('word', '').strip()
                        definition = entry.get('definition', '').strip()
                        
                        if not word or not definition:
                            error_count += 1
                            continue
                        
                        batch.append((word, definition))
                        
                        # Process batch
                        if len(batch) >= batch_size:
                            success, errors = self._process_import_batch(batch)
                            success_count += success
                            error_count += errors
                    
                    # Process remaining entries
                    if batch:
                        success, errors = self._process_import_batch(batch)
                        success_count += success
                        error_count += errors
            
            except ImportError:
                # Fallback to standard JSON parser for smaller files
                if large_file:
                    # For large files without ijson, use a chunked reader approach
                    return self._import_large_json_without_ijson(file_path)
                
                # Standard approach for smaller files
                with open(file_path, 'r', encoding='utf-8') as jsonfile:
                    data = json.load(jsonfile)
                    
                    # Check if data is a list
                    if not isinstance(data, list):
                        return {"success": 0, "error": 1, "message": "JSON must contain an array of word entries"}
                    
                    # Process entries in batches
                    batch_size = 100
                    total_entries = len(data)
                    batch = []
                    
                    for i, entry in enumerate(data):
                        # Update progress
                        progress_pct = (i + 1) / total_entries
                        if i % 100 == 0:
                            self.import_progress.value = progress_pct
                            self.import_feedback.value = f"Processing... {i + 1} of {total_entries} entries"
                            self.page.update()
                        
                        # Process entry
                        if not isinstance(entry, dict):
                            error_count += 1
                            continue
                            
                        word = entry.get('word', '').strip()
                        definition = entry.get('definition', '').strip()
                        
                        if not word or not definition:
                            error_count += 1
                            continue
                        
                        batch.append((word, definition))
                        
                        # Process batch
                        if len(batch) >= batch_size:
                            success, errors = self._process_import_batch(batch)
                            success_count += success
                            error_count += errors
                            batch = []
                    
                    # Process remaining entries
                    if batch:
                        success, errors = self._process_import_batch(batch)
                        success_count += success
                        error_count += errors
                
        except json.JSONDecodeError:
            raise Exception("Invalid JSON format")
        except Exception as e:
            raise Exception(f"Failed to process JSON file: {str(e)}")
        
        return {
            "success": success_count,
            "error": error_count,
            "message": f"Imported {success_count} words with {error_count} errors"
        }
    
    def _import_large_json_without_ijson(self, file_path):
        """Fallback method for importing large JSON files without ijson."""
        success_count = 0
        error_count = 0
        
        try:
            # Read and process the file in chunks
            chunk_size = 64 * 1024  # 64KB chunks
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                # First check that it's a JSON array
                first_char = f.read(1).strip()
                if first_char != '[':
                    return {"success": 0, "error": 1, "message": "JSON must start with an array '['"}
                
                # Reset to beginning
                f.seek(0)
                
                # Stream processing with manual JSON parsing
                in_string = False
                escape_next = False
                brace_level = 0
                current_object = ""
                processed_bytes = 0
                last_update = 0
                batch = []
                batch_size = 500
                
                # Read file in chunks
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                        
                    processed_bytes += len(chunk)
                    
                    # Update progress
                    progress_pct = processed_bytes / file_size
                    if progress_pct - last_update > 0.01:  # Update every 1%
                        self.import_progress.value = progress_pct
                        self.import_feedback.value = f"Processing... {progress_pct:.1%} complete"
                        self.page.update()
                        last_update = progress_pct
                    
                    # Process this chunk
                    for char in chunk:
                        # Skip array brackets at top level
                        if char == '[' and brace_level == 0:
                            continue
                        if char == ']' and brace_level == 0:
                            continue
                        
                        # Handle string escaping
                        if escape_next:
                            current_object += char
                            escape_next = False
                            continue
                            
                        if char == '\\':
                            current_object += char
                            escape_next = True
                            continue
                            
                        # Handle string boundaries
                        if char == '"' and not escape_next:
                            in_string = not in_string
                            current_object += char
                            continue
                            
                        # If in string, just append
                        if in_string:
                            current_object += char
                            continue
                            
                        # Track object nesting
                        if char == '{':
                            if brace_level == 0:
                                current_object = '{'  # Start a new object
                            else:
                                current_object += char
                            brace_level += 1
                        elif char == '}':
                            brace_level -= 1
                            current_object += char
                            
                            # Complete object found at top level
                            if brace_level == 0:
                                try:
                                    entry = json.loads(current_object)
                                    
                                    # Process the entry
                                    if isinstance(entry, dict):
                                        word = entry.get('word', '').strip()
                                        definition = entry.get('definition', '').strip()
                                        
                                        if word and definition:
                                            batch.append((word, definition))
                                            
                                            # Process batch if it's full
                                            if len(batch) >= batch_size:
                                                success, errors = self._process_import_batch(batch)
                                                success_count += success
                                                error_count += errors
                                    
                                except json.JSONDecodeError:
                                    error_count += 1
                                    
                                current_object = ""
                        elif char == ',' and brace_level == 0:
                            # Ignore commas between objects at top level
                            continue
                        else:
                            current_object += char
                
                # Process any remaining batch items
                if batch:
                    success, errors = self._process_import_batch(batch)
                    success_count += success
                    error_count += errors
        
        except Exception as e:
            raise Exception(f"Failed to process large JSON file: {str(e)}")
            
        return {
            "success": success_count,
            "error": error_count,
            "message": f"Imported {success_count} words with {error_count} errors"
        }
        
    def _process_import_batch(self, batch):
        """Process a batch of word imports.
        
        Args:
            batch: List of (word, definition) tuples
            
        Returns:
            Tuple of (success_count, error_count)
        """
        success_count = 0
        error_count = 0
        
        for word, definition in batch:
            if db.add_word(word, definition):
                success_count += 1
            else:
                error_count += 1
                
        return success_count, error_count

    def download_csv_template(self, e):
        """Create and download a CSV template file."""
        # Create template data
        template_data = "word,definition\nApple,A sweet red or green fruit.\nPython,A popular programming language."
        
        # Save to temporary file and prompt download
        self._download_template("lexicon_template.csv", template_data)
        
    def download_json_template(self, e):
        """Create and download a JSON template file."""
        # Create template data
        template_data = '''[
  {
    "word": "Apple",
    "definition": "A sweet red or green fruit."
  },
  {
    "word": "Python",
    "definition": "A popular programming language."
  }
]'''
        
        # Save to temporary file and prompt download
        self._download_template("lexicon_template.json", template_data)
        
    def _download_template(self, filename, content):
        """Helper method to download a template file."""
        # Create temporary file path
        temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        
        # Write template to file
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Show success message with snackbar
            self.show_snackbar(f"'{filename}' " + tr.get_text("template_success", self.current_language), self.primary_color)
            
            # Show more detailed notification dialog
            self.page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(tr.get_text("template_exported", self.current_language)),
                content=ft.Column([
                    ft.Text(f"'{filename}' " + tr.get_text("export_success", self.current_language)),
                    ft.Container(
                        content=ft.Text(temp_path, selectable=True),
                        bgcolor=ft.Colors.with_opacity(0.05, self.on_surface_color),
                        border_radius=10,
                        padding=10,
                        margin=ft.margin.only(top=10, bottom=10)
                    ),
                    ft.Text(tr.get_text("template_usage", self.current_language), size=14)
                ], tight=True, spacing=10),
                actions=[
                    ft.TextButton(tr.get_text("close", self.current_language), on_click=self.close_dialog)
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            if self.page.dialog not in self.page.controls:
                self.page.controls.append(self.page.dialog)
            self.page.dialog.open = True
            self.page.update()
        except Exception as e:
            # Show error message if export fails
            self.show_snackbar(f"{tr.get_text('error_exporting', self.current_language)}: {str(e)}", self.error_color)

    def on_search_field_change(self, e):
        """Throttled search handler to avoid too many updates while typing"""
        # If the field is empty, update immediately to show all words
        if e.control.value == "":
            self.update_search_results(e)
            return
            
        # Time-based throttling
        current_time = datetime.now()
        time_diff = (current_time - self.last_search_time).total_seconds()
        
        # Only update if enough time has passed since last update
        if time_diff >= self.search_throttle:
            self.update_search_results(e)
            self.last_search_time = current_time

    def handle_language_change(self, e):
        """Handle language change using proper key-value dropdown."""
        prev_language = self.current_language
        new_language = e.control.value
        
        print(f"Language changed from '{prev_language}' to '{new_language}'")
        print(f"Dropdown value type: {type(e.control.value)}")
        
        # Set the language directly (should already be a valid code)
        self.current_language = new_language
        
        # Refresh all UI text with new language
        self.refresh_ui_language()
        
        # Force a deep UI update to ensure all translations are properly applied
        self.force_ui_update()
        
        # Update the UI at the page level
        self.page.update()

    def force_ui_update(self):
        """Force a deep update of all UI elements to ensure language changes are applied."""
        # First make all sections visible temporarily
        original_visibilities = {}
        for i, section in enumerate(self.sections):
            original_visibilities[i] = section.visible
            section.visible = True
        
        # Update the page to render all sections
        self.page.update()
        
        # Short delay to allow rendering
        time.sleep(0.1)
        
        # Update nav bar and elements
        for i, dest in enumerate(self.nav_bar.destinations):
            if i == 0:
                dest.label = tr.get_text("search_tab", self.current_language)
            elif i == 1:
                dest.label = tr.get_text("add_tab", self.current_language)
            elif i == 2:
                dest.label = tr.get_text("settings_tab", self.current_language)
        
        # Reintialize the dropdown to force it to update
        language_options = tr.get_language_options()
        
        # Create options with correct format - key is language code, text is display name
        dropdown_options = []
        for lang in language_options:
            dropdown_options.append(ft.dropdown.Option(
                text=lang["name"],    # What user sees
                key=lang["code"]      # What's used internally
            ))
        
        # Update dropdown
        self.language_dropdown.options = dropdown_options
        self.language_dropdown.value = self.current_language
        self.language_dropdown.label = tr.get_text("language", self.current_language)
        
        # Force update import section text specifically
        try:
            import_section_controls = self.import_section.content.controls
            
            # Update import words title
            if len(import_section_controls) > 0:
                if isinstance(import_section_controls[0], ft.Row) and len(import_section_controls[0].controls) > 1:
                    import_section_controls[0].controls[1].value = tr.get_text("import_words", self.current_language)
            
            # Update import description
            if len(import_section_controls) > 1:
                if isinstance(import_section_controls[1], ft.Text):
                    import_section_controls[1].value = tr.get_text("import_description", self.current_language)
            
            # Update download templates row - specifically target row 6
            if len(import_section_controls) > 6:
                downloads_row = import_section_controls[6]
                if isinstance(downloads_row, ft.Row) and len(downloads_row.controls) > 1:
                    downloads_row.controls[1].value = tr.get_text("download_templates", self.current_language)
            
            # Update buttons
            self.import_button.text = tr.get_text("import_button", self.current_language)
            self.download_csv_button.text = tr.get_text("download_csv_template", self.current_language)
            self.download_json_button.text = tr.get_text("download_json_template", self.current_language)
        except Exception as ex:
            print(f"Error updating import section in force_ui_update: {ex}")
        
        # Force update
        self.page.update()
        
        # Restore original visibility state
        for i, visible in original_visibilities.items():
            self.sections[i].visible = visible
        
        # Final update
        self.page.update()

    def refresh_ui_language(self):
        """Refresh all UI text based on current language. Can be called after changing language or initialization."""
        # Verify language code is valid
        if self.current_language not in [lang["code"] for lang in tr.get_language_options()]:
            print(f"Invalid language in refresh_ui_language: {self.current_language}")
            self.current_language = tr.DEFAULT_LANGUAGE
        
        print(f"Refreshing UI with language: {self.current_language}")
            
        # Update app title
        self.page.title = tr.get_text("app_name", self.current_language)
        
        # Update app bar
        self.app_bar.title.value = tr.get_text("app_name", self.current_language)
        self.app_bar.actions[0].tooltip = tr.get_text("dark_mode", self.current_language)
        self.app_bar.actions[1].tooltip = tr.get_text("about", self.current_language)
        
        # Update navigation bar
        for i, dest in enumerate(self.nav_bar.destinations):
            if i == 0:
                dest.label = tr.get_text("search_tab", self.current_language)
            elif i == 1:
                dest.label = tr.get_text("add_tab", self.current_language)
            elif i == 2:
                dest.label = tr.get_text("settings_tab", self.current_language)
        
        # Update search section
        self.search_field.label = tr.get_text("search_placeholder", self.current_language)
        
        # Update definition panel buttons
        definition_controls = self.definition_panel.content.controls[0].controls
        if len(definition_controls) >= 4:  # Make sure all controls exist
            definition_controls[1].tooltip = tr.get_text("edit", self.current_language)
            definition_controls[2].tooltip = tr.get_text("delete", self.current_language)
            definition_controls[3].tooltip = tr.get_text("close", self.current_language)
        
        # If a word is currently displayed, update the "Added on" text
        if self.current_word and self.definition_panel.visible:
            date_label = self.definition_panel.content.controls[3]
            date_label.value = f"{tr.get_text('added_on', self.current_language)} {self.current_word['date_added']}"
        
        # Update add section
        self.add_word_field.label = tr.get_text("word_label", self.current_language)
        self.add_def_field.label = tr.get_text("definition_label", self.current_language)
        self.add_button.text = tr.get_text("add_word_button", self.current_language)
        
        # Update settings section
        self.dark_mode_switch.label = tr.get_text("dark_mode", self.current_language)
        self.language_dropdown.label = tr.get_text("language", self.current_language)
        
        # Ensure dropdown is set to the correct language
        if self.language_dropdown.value != self.current_language:
            self.language_dropdown.value = self.current_language
        
        # Update import section components
        try:
            # Update dropdown and its container
            dropdown = self.import_format_dropdown.content
            dropdown.label = tr.get_text("import_format", self.current_language)
            self.import_format_dropdown.tooltip = tr.get_text("import_description", self.current_language)
            
            # Update buttons
            self.import_button.text = tr.get_text("import_button", self.current_language)
            self.download_csv_button.text = tr.get_text("download_csv_template", self.current_language)
            self.download_json_button.text = tr.get_text("download_json_template", self.current_language)
            
            # Update import section headers and text
            import_section_controls = self.import_section.content.controls
            if len(import_section_controls) > 0:
                header_row = import_section_controls[0]
                if isinstance(header_row, ft.Row) and len(header_row.controls) > 1:
                    header_row.controls[1].value = tr.get_text("import_words", self.current_language)
                
                if len(import_section_controls) > 1:
                    description_text = import_section_controls[1]
                    if isinstance(description_text, ft.Text):
                        description_text.value = tr.get_text("import_description", self.current_language)
                
                # Find and update download templates text
                # Get specific row 6 which is the download templates row
                downloads_row = import_section_controls[6] if len(import_section_controls) > 6 else None
                if downloads_row and isinstance(downloads_row, ft.Row) and len(downloads_row.controls) > 1:
                    downloads_row.controls[1].value = tr.get_text("download_templates", self.current_language)
                    # Force update this control specifically
                    downloads_row.controls[1].update()
        except Exception as ex:
            print(f"Error updating import section: {ex}")
        
        # Update about info in settings section
        try:
            about_container = self.settings_section.content.controls[0].controls[0].content.controls
            if len(about_container) > 3:
                about_info = about_container[3]  # The ListTile
                about_info.title.value = tr.get_text("app_name", self.current_language)
                about_info.subtitle.value = tr.get_text("version", self.current_language)
                about_info.trailing.value = tr.get_text("copyright", self.current_language)
        except Exception as ex:
            print(f"Error updating about info: {ex}")


async def app_start(page: ft.Page):
    # Migrate sample data to database if needed
    migrate_sample_data()
    
    # Create and show splash screen
    splash = SplashScreen(page)
    splash_task = asyncio.create_task(splash.show())

    # Wait for 2.5 seconds
    await asyncio.sleep(2.5)

    # Hide splash screen
    await splash.hide()
    splash_task.cancel()

    # Initialize the app
    DictionaryApp(page)


ft.app(target=app_start)